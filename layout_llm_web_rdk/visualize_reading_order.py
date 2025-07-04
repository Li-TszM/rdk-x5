#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于textboxes_with_reading_order.json生成可视化图片
生成两张PNG图片：
1. 以文本框为基准的阅读顺序可视化
2. 以块为基准的阅读顺序可视化

支持两种输入模式：
1. PDF文件：自动转换为图片后进行可视化
2. 图片目录：直接使用现有的页面图片

使用方法：
1. 使用PDF文件作为输入：
   python visualize_reading_order.py --json textboxes_with_reading_order.json --input demo.pdf --output output_dir

2. 使用图片目录作为输入：
   python visualize_reading_order.py --json textboxes_with_reading_order.json --input pages_dir --output output_dir

3. 无参数运行（使用默认配置）：
   python visualize_reading_order.py

依赖要求：
- 基本依赖：opencv-python, numpy, matplotlib
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
import matplotlib.pyplot as plt
import matplotlib.patches as patches
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

def visualize_textboxes_reading_order(data, page_images, output_dir):
    """生成以文本框为基准的阅读顺序可视化"""
    print("\n=== 生成文本框阅读顺序可视化 ===")
    
    os.makedirs(output_dir, exist_ok=True)
    
    for page_data in data["pages"]:
        page_idx = page_data["page_index"]
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
        for block in page_data["blocks"]:
            for textbox in block["contained_text_boxes"]:
                if "bbox" in textbox and "page_reading_order" in textbox:
                    all_textboxes.append({
                        "bbox": textbox["bbox"],
                        "page_reading_order": textbox["page_reading_order"],
                        "global_reading_order": textbox.get("global_reading_order", -1),
                        "is_virtual": textbox.get("is_virtual", False),
                        "transcription": textbox.get("transcription", "")
                    })
        
        if not all_textboxes:
            print(f"  页面 {page_idx} 没有有效的文本框")
            continue
        
        print(f"  处理 {len(all_textboxes)} 个文本框")
        
        # 生成颜色
        max_order = max(tb["page_reading_order"] for tb in all_textboxes if tb["page_reading_order"] >= 0)
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
            
            # 选择颜色和样式
            if order >= 0 and order < len(colors):
                color = colors[order]
            else:
                color = [128, 128, 128]  # 灰色表示无效顺序
            
            # 虚拟文本框使用虚线边框
            if is_virtual:
                # 绘制虚线边框
                dash_length = 10
                for i in range(0, x2 - x1, dash_length * 2):
                    cv2.line(img, (x1 + i, y1), (x1 + min(i + dash_length, x2 - x1), y1), color, 2)
                    cv2.line(img, (x1 + i, y2), (x1 + min(i + dash_length, x2 - x1), y2), color, 2)
                for i in range(0, y2 - y1, dash_length * 2):
                    cv2.line(img, (x1, y1 + i), (x1, y1 + min(i + dash_length, y2 - y1)), color, 2)
                    cv2.line(img, (x2, y1 + i), (x2, y1 + min(i + dash_length, y2 - y1)), color, 2)
                
                # 添加半透明填充
                overlay = img.copy()
                cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
                cv2.addWeighted(overlay, 0.2, img, 0.8, 0, img)
            else:
                # 真实文本框使用实线边框
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
        

        
        # 保存图像
        output_path = os.path.join(output_dir, f"textbox_reading_order_page_{page_idx}.png")
        cv2.imwrite(output_path, img)
        print(f"  保存文本框可视化: {output_path}")

def visualize_blocks_reading_order(data, page_images, output_dir):
    """生成以块为基准的阅读顺序可视化"""
    print("\n=== 生成块阅读顺序可视化 ===")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 预定义块类型颜色
    block_type_colors = {
        "title": [255, 0, 0],           # 红色
        "plain text": [0, 128, 255],   # 蓝色
        "figure": [0, 255, 0],          # 绿色
        "table": [255, 165, 0],         # 橙色
        "isolate_formula": [255, 0, 255], # 洋红
        "figure_caption": [128, 0, 128], # 紫色
        "abandon": [128, 128, 128],     # 灰色
        "default": [64, 64, 64]         # 深灰色
    }
    
    for page_data in data["pages"]:
        page_idx = page_data["page_index"]
        print(f"\n处理第 {page_idx + 1} 页")
        
        # 获取页面图像
        if page_idx in page_images:
            img = page_images[page_idx].copy()
        else:
            # 如果没有页面图像，创建空白图像
            img = np.ones((2200, 1700, 3), dtype=np.uint8) * 255
            print(f"  使用默认空白图像 (页面 {page_idx})")
        
        height, width = img.shape[:2]
        
        # 收集所有块信息
        blocks_info = []
        for block in page_data["blocks"]:
            block_info = block.get("block_info", {})
            if "bbox" in block_info and "page_block_order" in block_info:
                blocks_info.append({
                    "bbox": block_info["bbox"],
                    "class_name": block_info.get("class_name", "unknown"),
                    "page_block_order": block_info["page_block_order"],
                    "textbox_reading_order_median": block_info.get("textbox_reading_order_median", -1),
                    "textbox_count": block_info.get("contained_text_count", 0),
                    "is_virtual_text": block_info.get("is_virtual_text", False),
                    "crop_image_path": block_info.get("crop_image_path", "")
                })
        
        if not blocks_info:
            print(f"  页面 {page_idx} 没有有效的块")
            continue
        
        print(f"  处理 {len(blocks_info)} 个块")
        
        # 绘制块
        for block in blocks_info:
            bbox = block["bbox"]
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
            
            class_name = block["class_name"]
            order = block["page_block_order"]
            median_order = block["textbox_reading_order_median"]
            is_virtual = block["is_virtual_text"]
            has_crop = bool(block["crop_image_path"])
            
            # 选择颜色
            color = block_type_colors.get(class_name, block_type_colors["default"])
            
            # 特殊类型块（figure、table、isolate_formula）使用不同的边框样式
            if class_name.lower() in ["figure", "table", "isolate_formula"]:
                # 使用粗边框
                border_thickness = 4
                if has_crop:
                    # 有切割图像的块使用双边框
                    cv2.rectangle(img, (x1-2, y1-2), (x2+2, y2+2), [0, 0, 0], 2)  # 外框
                    cv2.rectangle(img, (x1, y1), (x2, y2), color, border_thickness)  # 内框
                else:
                    cv2.rectangle(img, (x1, y1), (x2, y2), color, border_thickness)
            else:
                # 普通块使用正常边框
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
            
            # 添加半透明填充
            overlay = img.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            alpha = 0.15 if is_virtual else 0.25
            cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
            
            # 绘制块的阅读顺序信息
            # 主要显示页面块顺序
            main_text = f"B{order}"
            if median_order >= 0:
                main_text += f"\nM{median_order:.1f}"
            
            # 计算文本位置
            text_lines = main_text.split('\n')
            line_height = 25
            total_height = len(text_lines) * line_height
            
            # 文本位置在块的左上角
            text_x = x1 + 10
            text_y = y1 + 30
            
            # 绘制文本背景
            bg_width = 80
            bg_height = total_height + 20
            cv2.rectangle(img, 
                         (text_x - 5, text_y - 25), 
                         (text_x + bg_width, text_y + bg_height - 25), 
                         (255, 255, 255), -1)
            cv2.rectangle(img, 
                         (text_x - 5, text_y - 25), 
                         (text_x + bg_width, text_y + bg_height - 25), 
                         (0, 0, 0), 1)
            
            # 绘制文本
            for i, line in enumerate(text_lines):
                cv2.putText(img, line, (text_x, text_y + i * line_height), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            
            # 在块的右上角显示类型
            type_text = class_name[:8] + ("..." if len(class_name) > 8 else "")
            type_size = cv2.getTextSize(type_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            type_x = x2 - type_size[0] - 10
            type_y = y1 + 20
            
            cv2.rectangle(img, 
                         (type_x - 3, type_y - 15), 
                         (type_x + type_size[0] + 3, type_y + 3), 
                         (255, 255, 255), -1)
            cv2.putText(img, type_text, (type_x, type_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        

        
        # 保存图像
        output_path = os.path.join(output_dir, f"block_reading_order_page_{page_idx}.png")
        cv2.imwrite(output_path, img)
        print(f"  保存块可视化: {output_path}")



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
    parser = argparse.ArgumentParser(description='生成阅读顺序可视化图片')
    parser.add_argument('--json', required=False, 
                       help='包含阅读顺序信息的JSON文件路径')
    parser.add_argument('--input', required=False,
                       help='输入源：PDF文件路径或页面图片目录')
    parser.add_argument('--output', required=False,
                       help='输出目录路径')
    parser.add_argument('--dpi', type=int, default=200,
                       help='PDF转换图片时的DPI (默认: 200)')
    parser.add_argument('--temp-dir', 
                       help='PDF转换时的临时目录 (默认: output_dir/temp_pages)')
    parser.add_argument('--project', type=str, default="demo",
                       help='项目名称，用于生成默认路径 (默认: demo)')
    
    # 如果没有提供参数，使用默认值（保持向后兼容）
    if len(sys.argv) == 1:
        print("使用默认配置运行...")
        project_name = "demo"
        json_file = f"/home/m/Documents/layout_llm_web/layout_process/results/{project_name}/temp/{project_name}_sorted.json"
        input_source = f"/home/m/Documents/layout_llm_web/layout_process/data/{project_name}.pdf"  # 优先使用PDF
        output_dir = f"/home/m/Documents/layout_llm_web/results/{project_name}/visualization_output"
        dpi = 200
        temp_dir = None
    else:
        args = parser.parse_args()
        project_name = args.project
        
        # 如果用户提供了具体路径，使用用户提供的；否则使用项目名称生成默认路径
        if args.json:
            json_file = args.json
        else:
            json_file = f"/home/m/Documents/layout_llm_web/layout_process/results/{project_name}/temp/{project_name}_sorted.json"
        
        if args.input:
            input_source = args.input
        else:
            input_source = f"/home/m/Documents/layout_llm_web/layout_process/data/{project_name}.pdf"
        
        if args.output:
            output_dir = args.output
        else:
            output_dir = f"/home/m/Documents/layout_llm_web/results/{project_name}/visualization_output"
        
        dpi = args.dpi
        temp_dir = args.temp_dir
    
    # 检查输入文件
    if not os.path.exists(json_file):
        print(f"错误: JSON文件不存在 {json_file}")
        return
    
    if not os.path.exists(input_source):
        print(f"错误: 输入源不存在 {input_source}")
        return
    
    print("=== 阅读顺序可视化脚本 ===")
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
            data = json.load(f)
        
        print(f"加载完成，共 {data['metadata']['total_pages']} 页")
        
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
            print("警告: 没有找到任何页面图像")
        
        # 生成文本框可视化
        visualize_textboxes_reading_order(data, page_images, output_dir)
        
        # 生成块可视化
        visualize_blocks_reading_order(data, page_images, output_dir)
        
        print(f"\n=== 可视化完成 ===")
        print(f"所有文件已保存到: {output_dir}")
        
        # 如果使用了临时目录，询问是否删除
        if input_type == 'pdf' and temp_dir and os.path.exists(temp_dir):
            print(f"\n临时页面图片保存在: {temp_dir}")
            print("您可以手动删除这些临时文件，或保留它们以备后用。")
        
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        
        print(f"\n=== 可视化完成 ===")
        print(f"所有文件已保存到: {output_dir}")
        
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
