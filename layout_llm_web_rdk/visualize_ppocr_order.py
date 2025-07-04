#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于scan_ppocr_bbox.json生成文本框阅读顺序可视化图片

支持两种输入模式：
1. PDF文件：自动转换为图片后进行可视化
2. 图片目录：直接使用现有的页面图片

使用方法：
1. 使用PDF文件作为输入：
   python visualize_ppocr_order.py --json scan_ppocr_bbox.json --input demo.pdf --output output_dir

2. 使用图片目录作为输入：
   python visualize_ppocr_order.py --json scan_ppocr_bbox.json --input pages_dir --output output_dir

3. 无参数运行（使用默认配置）：
   python visualize_ppocr_order.py

依赖要求：
- 基本依赖：opencv-python, numpy
- PDF处理（可选）：PyMuPDF 或 pdf2image
  pip install PyMuPDF  # 推荐
  或
  pip install pdf2image  # 需要额外安装 poppler-utils
"""

import os
import json
import cv2
import numpy as np
from pathlib import Path
from matplotlib.colors import hsv_to_rgb
import random
import argparse
import sys

# 尝试导入PDF处理库
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

def load_page_images(pages_dir):
    """加载页面图像"""
    page_images = {}
    pages_path = Path(pages_dir)
    
    if not pages_path.exists():
        print(f"警告: 页面图像目录不存在: {pages_dir}")
        return page_images
    
    # 查找页面图像文件
    for img_file in pages_path.glob("page_*.png"):
        try:
            page_idx = int(img_file.stem.split('_')[1])
            img = cv2.imread(str(img_file))
            if img is not None:
                page_images[page_idx] = img
                print(f"加载页面图像: {img_file.name} -> 页面 {page_idx}")
        except (ValueError, IndexError) as e:
            print(f"跳过无效文件名: {img_file.name} - {e}")
    
    return page_images

def generate_colors(n):
    """生成n个不同的颜色"""
    colors = []
    for i in range(n):
        hue = i / n
        saturation = 0.7 + 0.3 * random.random()
        value = 0.8 + 0.2 * random.random()
        rgb = hsv_to_rgb([hue, saturation, value])
        colors.append([int(c * 255) for c in rgb])
    return colors

def group_blocks_by_page(blocks_data):
    """按页面分组块数据"""
    pages = {}
    for block in blocks_data:
        page_idx = block.get("page_idx", 0)
        if page_idx not in pages:
            pages[page_idx] = []
        pages[page_idx].append(block)
    return pages

def visualize_textboxes_reading_order(blocks_data, page_images, output_dir):
    """生成以文本框为基准的阅读顺序可视化"""
    print("\n=== 生成文本框阅读顺序可视化 ===")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 按页面分组
    pages = group_blocks_by_page(blocks_data)
    
    for page_idx, page_blocks in pages.items():
        print(f"\n处理第 {page_idx + 1} 页")
        
        # 获取页面图像
        if page_idx in page_images:
            img = page_images[page_idx].copy()
        else:
            # 如果没有页面图像，创建空白图像
            img = np.ones((2200, 1700, 3), dtype=np.uint8) * 255
            print(f"  使用默认空白图像 (页面 {page_idx})")
        
        height, width = img.shape[:2]
        
        # 收集所有文本框信息
        all_textboxes = []
        for i, block in enumerate(page_blocks):
            bbox = block.get("bbox", [])
            if len(bbox) >= 4:
                all_textboxes.append({
                    "bbox": bbox,
                    "page_reading_order": i,  # 使用在页面中的顺序作为阅读顺序
                    "global_reading_order": -1,
                    "is_virtual": False,
                    "transcription": block.get("text", ""),
                    "class_name": block.get("class_name", "text"),
                    "score": block.get("score", 0.0)
                })
        
        if not all_textboxes:
            print(f"  页面 {page_idx} 没有有效的文本框")
            continue
        
        print(f"  处理 {len(all_textboxes)} 个文本框")
        
        # 生成颜色
        max_order = len(all_textboxes) - 1
        colors = generate_colors(max_order + 1)
        
        # 绘制文本框
        for textbox in all_textboxes:
            bbox = textbox["bbox"]
            if len(bbox) < 4:
                continue
            
            x1, y1, x2, y2 = map(int, bbox[:4])
            
            # 确保坐标在图像范围内
            x1 = max(0, min(x1, width))
            y1 = max(0, min(y1, height))
            x2 = max(0, min(x2, width))
            y2 = max(0, min(y2, height))
            
            if x2 <= x1 or y2 <= y1:
                continue
            
            order = textbox["page_reading_order"]
            is_virtual = textbox["is_virtual"]
            class_name = textbox["class_name"]
            
            # 选择颜色和样式
            if order >= 0 and order < len(colors):
                color = colors[order]
            else:
                color = [128, 128, 128]  # 灰色表示无效顺序
            
            # 绘制边框（所有文本框都使用实线边框）
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            
            # 添加半透明填充
            overlay = img.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)
            
            # 绘制阅读顺序编号
            text = str(order) if order >= 0 else "?"
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            text_x = x1 + (x2 - x1 - text_size[0]) // 2
            text_y = y1 + (y2 - y1 + text_size[1]) // 2
            
            # 绘制文本背景
            cv2.rectangle(img, 
                         (text_x - 5, text_y - text_size[1] - 5), 
                         (text_x + text_size[0] + 5, text_y + 5), 
                         (255, 255, 255), -1)
            cv2.rectangle(img, 
                         (text_x - 5, text_y - text_size[1] - 5), 
                         (text_x + text_size[0] + 5, text_y + 5), 
                         (0, 0, 0), 1)
            
            # 绘制文本
            cv2.putText(img, text, (text_x, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
            
            # 在文本框右上角显示类型
            if class_name and class_name != "text":
                type_text = class_name[:6] + ("..." if len(class_name) > 6 else "")
                type_size = cv2.getTextSize(type_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                type_x = x2 - type_size[0] - 5
                type_y = y1 + 20
                
                cv2.rectangle(img, 
                             (type_x - 2, type_y - 15), 
                             (type_x + type_size[0] + 2, type_y + 2), 
                             (255, 255, 255), -1)
                cv2.putText(img, type_text, (type_x, type_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # 保存图像
        output_path = os.path.join(output_dir, f"textbox_reading_order_page_{page_idx}.png")
        cv2.imwrite(output_path, img)
        print(f"  保存文本框可视化: {output_path}")

def convert_pdf_to_images(pdf_path, output_dir, dpi=200):
    """
    将PDF转换为图片
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        dpi: 图片分辨率
    
    Returns:
        dict: 页面索引到图片路径的映射
    """
    print(f"\n=== 转换PDF为图片 ===")
    print(f"PDF文件: {pdf_path}")
    print(f"输出目录: {output_dir}")
    print(f"分辨率: {dpi} DPI")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    page_images = {}
    
    # 优先使用 PyMuPDF (fitz)
    if HAS_PYMUPDF:
        print("使用 PyMuPDF 进行转换...")
        try:
            pdf_doc = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_doc)):
                print(f"  转换第 {page_num + 1} 页...")
                
                # 设置缩放因子以达到指定DPI
                zoom = dpi / 72.0  # 72 是PDF的默认DPI
                mat = fitz.Matrix(zoom, zoom)
                
                page = pdf_doc.load_page(page_num)
                pix = page.get_pixmap(matrix=mat)
                
                # 保存为PNG
                output_path = os.path.join(output_dir, f"page_{page_num}.png")
                pix.save(output_path)
                
                # 加载图片到内存
                img = cv2.imread(output_path)
                if img is not None:
                    page_images[page_num] = img
                    print(f"    保存: {output_path}")
                else:
                    print(f"    警告: 无法加载生成的图片 {output_path}")
            
            pdf_doc.close()
            print(f"PyMuPDF 转换完成，共转换 {len(page_images)} 页")
            return page_images
            
        except Exception as e:
            print(f"PyMuPDF 转换失败: {e}")
    
    # 备选方案：使用 pdf2image
    if HAS_PDF2IMAGE:
        print("使用 pdf2image 进行转换...")
        try:
            pages = convert_from_path(pdf_path, dpi=dpi)
            
            for page_num, page in enumerate(pages):
                print(f"  转换第 {page_num + 1} 页...")
                
                # 保存为PNG
                output_path = os.path.join(output_dir, f"page_{page_num}.png")
                page.save(output_path, 'PNG')
                
                # 加载图片到内存
                img = cv2.imread(output_path)
                if img is not None:
                    page_images[page_num] = img
                    print(f"    保存: {output_path}")
                else:
                    print(f"    警告: 无法加载生成的图片 {output_path}")
            
            print(f"pdf2image 转换完成，共转换 {len(page_images)} 页")
            return page_images
            
        except Exception as e:
            print(f"pdf2image 转换失败: {e}")
    
    # 如果两种方法都失败
    print("错误: 无法转换PDF文件")
    print("请安装以下依赖之一:")
    print("  - PyMuPDF: pip install PyMuPDF")
    print("  - pdf2image: pip install pdf2image (还需要 poppler-utils)")
    return {}

def check_pdf_dependencies():
    """检查PDF处理依赖"""
    if not HAS_PYMUPDF and not HAS_PDF2IMAGE:
        print("警告: 未安装PDF处理库")
        print("为了处理PDF文件，请安装以下依赖之一:")
        print("  1. PyMuPDF (推荐): pip install PyMuPDF")
        print("  2. pdf2image: pip install pdf2image")
        print("     注意: pdf2image 还需要安装 poppler-utils")
        print("           Ubuntu/Debian: sudo apt-get install poppler-utils")
        print("           CentOS/RHEL: sudo yum install poppler-utils")
        return False
    return True

def detect_input_type(input_path):
    """检测输入类型：PDF文件还是图片目录"""
    input_path = Path(input_path)
    
    if input_path.is_file() and input_path.suffix.lower() == '.pdf':
        return 'pdf'
    elif input_path.is_dir():
        # 检查是否包含页面图片
        page_files = list(input_path.glob("page_*.png"))
        if page_files:
            return 'directory'
    
    return 'unknown'

def main():
    """主函数"""
    # 设置命令行参数
    parser = argparse.ArgumentParser(description='生成PPOCR文本框阅读顺序可视化图片')
    parser.add_argument('--json', 
                       help='包含PPOCR数据的JSON文件路径')
    parser.add_argument('--input',
                       help='输入源：PDF文件路径或页面图片目录')
    parser.add_argument('--output',
                       help='输出目录路径')
    parser.add_argument('--dpi', type=int, default=200,
                       help='PDF转换图片时的DPI (默认: 200)')
    parser.add_argument('--temp-dir', 
                       help='PDF转换时的临时目录 (默认: output_dir/temp_pages)')
    
    # 如果没有提供参数，使用默认值（保持向后兼容）
    if len(sys.argv) == 1:
        print("使用默认配置运行...")
        json_file = "/home/m/Downloads/layout/results/BERT/temp/BERT_ppocr_bbox.json"
        input_source = "/home/m/Downloads/layout/data/BERT.pdf"  # 优先使用已有图片
        output_dir = "/home/m/Downloads/layout/results/BERT/ppocr_order"
        dpi = 200
        temp_dir = None
    else:
        args = parser.parse_args()
        json_file = args.json or "/home/m/Downloads/layout/results/scan/temp/scan_ppocr_bbox.json"
        input_source = args.input or "/home/m/Downloads/layout/layout_analyzer/output/pages"
        output_dir = args.output or "/home/m/Downloads/layout/results/scan/ppocr_order"
        dpi = args.dpi
        temp_dir = args.temp_dir
    
    # 检查输入文件
    if not os.path.exists(json_file):
        print(f"错误: JSON文件不存在 {json_file}")
        return
    
    if not os.path.exists(input_source):
        print(f"错误: 输入源不存在 {input_source}")
        return
    
    print("=== PPOCR 可视化脚本 ===")
    print(f"输入JSON: {json_file}")
    print(f"输入源: {input_source}")
    print(f"输出目录: {output_dir}")
    
    # 检测输入类型
    input_type = detect_input_type(input_source)
    print(f"输入类型: {input_type}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 读取JSON数据
        print("\n加载JSON数据...")
        with open(json_file, 'r', encoding='utf-8') as f:
            blocks_data = json.load(f)
        
        print(f"加载完成，共 {len(blocks_data)} 个文本块")
        
        # 统计页面数量
        pages = group_blocks_by_page(blocks_data)
        print(f"发现 {len(pages)} 个页面")
        
        # 根据输入类型处理页面图像
        page_images = {}
        
        if input_type == 'pdf':
            # 处理PDF文件
            if not check_pdf_dependencies():
                print("错误: 缺少PDF处理依赖，无法处理PDF文件")
                return
            
            # 设置临时目录
            if temp_dir is None:
                temp_dir = os.path.join(output_dir, "temp_pages")
            
            print(f"PDF转换临时目录: {temp_dir}")
            
            # 转换PDF为图片
            page_images = convert_pdf_to_images(input_source, temp_dir, dpi)
            
            if not page_images:
                print("错误: PDF转换失败，无法继续")
                return
                
        elif input_type == 'directory':
            # 处理图片目录
            print("\n加载页面图像...")
            page_images = load_page_images(input_source)
            
        else:
            print(f"错误: 无法识别的输入类型 {input_source}")
            print("输入应该是:")
            print("  - PDF文件 (.pdf)")
            print("  - 包含页面图片的目录 (包含 page_*.png 文件)")
            return
        
        print(f"加载了 {len(page_images)} 个页面图像")
        
        if not page_images:
            print("警告: 没有找到任何页面图像，将使用空白图像")
        
        # 生成文本框可视化
        visualize_textboxes_reading_order(blocks_data, page_images, output_dir)
        
        print(f"\n=== 文本框阅读顺序可视化完成 ===")
        print(f"所有文件已保存到: {output_dir}")
        
        # 如果使用了临时目录，询问是否删除
        if input_type == 'pdf' and temp_dir and os.path.exists(temp_dir):
            print(f"\n临时页面图片保存在: {temp_dir}")
            print("您可以手动删除这些临时文件，或保留它们以备后用。")
        
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
