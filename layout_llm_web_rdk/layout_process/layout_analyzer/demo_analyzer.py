# -*- encoding: utf-8 -*-
# @Author: layout_analyzer
# 版面分析功能演示

import os
import argparse
from pathlib import Path
import json
import shutil  # 添加这个导入

import cv2

from layout_analyzer import LayoutAnalyzer


def save_blocks_info_only(blocks, output_dir, page_idx=None):
    """仅保存版面块信息，不保存图像和切割块"""
    blocks_info = []
    
    # 保存版面块信息
    for i, block in enumerate(blocks):
        x1, y1, x2, y2 = map(int, block.box)
        
        block_info = {
            "block_idx": i,
            "class_name": block.class_name,
            "bbox": [x1, y1, x2, y2],
            "score": float(block.score),
            "page_idx": page_idx if page_idx is not None else 0
        }
        
        blocks_info.append(block_info)
    
    return blocks_info


def save_blocks_info_with_crops(blocks, img, output_dir, page_idx=None):
    """保存版面块信息并切割特定类型的块，但不保存完整页面图像"""
    # 将BGR格式转换为RGB格式
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    blocks_info = []
    
    # 创建crops文件夹
    crops_dir = os.path.join(output_dir, "crops")
    os.makedirs(crops_dir, exist_ok=True)
    
    # 定义需要切割的块类型
    crop_types = {"figure", "isolate_formula", "table"}
    
    # 保存版面块信息并切割特定类型的块
    for i, block in enumerate(blocks):
        x1, y1, x2, y2 = map(int, block.box)
        
        # 确保坐标在图像范围内
        h, w = img.shape[:2]
        x1 = max(0, min(x1, w))
        y1 = max(0, min(y1, h))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))
        
        block_info = {
            "class_name": block.class_name,
            "bbox": [x1, y1, x2, y2],
            "score": float(block.score),
            "block_idx": i
        }
        if page_idx is not None:
            block_info["page_idx"] = page_idx  # 页码从0开始
        
        # 如果是需要切割的类型，保存切割图像
        if block.class_name.lower() in crop_types:
            # 切割图像区域
            if x2 > x1 and y2 > y1:  # 确保有效的边界框
                cropped_img = img[y1:y2, x1:x2]
                
                # 生成切割图像的文件名
                if page_idx is not None:
                    crop_filename = f"page_{page_idx}_{block.class_name}_{i}.png"
                else:
                    crop_filename = f"{block.class_name}_{i}.png"
                
                crop_path = os.path.join(crops_dir, crop_filename)
                cv2.imwrite(crop_path, cropped_img)
                
                # 在块信息中添加切割图像路径
                block_info["crop_image_path"] = crop_path
                # print(f"已保存切割图像: {crop_path} ({block.class_name})")
        
        blocks_info.append(block_info)
    
    return blocks_info


def save_blocks_info_and_page_image(blocks, img, output_dir, page_idx=None):
    """保存版面块信息和完整页面图像，并切割特定类型的块"""
    # 将BGR格式转换为RGB格式
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    blocks_info = []
    
    # 创建crops和pages文件夹
    crops_dir = os.path.join(output_dir, "crops")
    pages_dir = os.path.join(output_dir, "pages")
    os.makedirs(crops_dir, exist_ok=True)
    os.makedirs(pages_dir, exist_ok=True)
    
    # 保存完整页面图像到pages文件夹
    if page_idx is not None:
        page_image_name = f"page_{page_idx}.png"
        page_image_path = os.path.join(pages_dir, page_image_name)
        cv2.imwrite(page_image_path, img)
        # print(f"已保存页面图像: {page_image_path}")
    else:
        page_image_name = "image.png"
        page_image_path = os.path.join(pages_dir, page_image_name)
        cv2.imwrite(page_image_path, img)
        # print(f"已保存图像: {page_image_path}")
    
    # 定义需要切割的块类型
    crop_types = {"figure", "isolate_formula", "table"}
    
    # 保存版面块信息并切割特定类型的块
    for i, block in enumerate(blocks):
        x1, y1, x2, y2 = map(int, block.box)
        
        # 确保坐标在图像范围内
        h, w = img.shape[:2]
        x1 = max(0, min(x1, w))
        y1 = max(0, min(y1, h))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))
        
        block_info = {
            "class_name": block.class_name,
            "bbox": [x1, y1, x2, y2],
            "score": float(block.score),
            "block_idx": i
        }
        if page_idx is not None:
            block_info["page_idx"] = page_idx  # 页码从0开始
        
        # 如果是需要切割的类型，保存切割图像
        if block.class_name.lower() in crop_types:
            # 切割图像区域
            if x2 > x1 and y2 > y1:  # 确保有效的边界框
                cropped_img = img[y1:y2, x1:x2]
                
                # 生成切割图像的文件名
                if page_idx is not None:
                    crop_filename = f"page_{page_idx}_{block.class_name}_{i}.png"
                else:
                    crop_filename = f"{block.class_name}_{i}.png"
                
                crop_path = os.path.join(crops_dir, crop_filename)
                cv2.imwrite(crop_path, cropped_img)
                
                # 在块信息中添加切割图像路径
                block_info["crop_image_path"] = crop_path
                # print(f"已保存切割图像: {crop_path} ({block.class_name})")
        
        blocks_info.append(block_info)
    
    return blocks_info


def clear_output_directory(output_dir):
    """清理输出目录中的所有文件"""
    if os.path.exists(output_dir):
        # 删除整个目录及其内容
        shutil.rmtree(output_dir)
    # 重新创建空目录
    os.makedirs(output_dir, exist_ok=True)
    # print(f"已清理输出目录: {output_dir}")


def analyze_pdf_demo(pdf_path, output_dir, model_type, conf_thres, iou_thres, use_cuda):
    """PDF版面分析演示 - 进行版面分析并切割特定类型的块"""
    # print(f"正在分析PDF文件: {pdf_path}")
    
    # 清理输出目录
    clear_output_directory(output_dir)
    
    # 创建版面分析器
    analyzer = LayoutAnalyzer(
        model_type=model_type,
        conf_thres=conf_thres,
        iou_thres=iou_thres,
        use_cuda=use_cuda
    )
    
    # 分析PDF - 进行版面分析并切割特定类型的块
    result = analyzer.analyze_pdf(pdf_path)
    
    print(f"PDF共有 {result.total_pages} 页，分析了 {len(result.page_results)} 页")
    
    all_blocks_info = []
    crop_counts = {"figure": 0, "isolate_formula": 0, "table": 0}  # 统计识别的版面块数量
    
    # 打印每页的版面块信息并保存切割图像
    for page_result in result.page_results:
        print(f"\n第 {page_result.page_idx + 1} 页:")
        blocks_by_class = {}
        
        for block in page_result.blocks:
            if block.class_name not in blocks_by_class:
                blocks_by_class[block.class_name] = []
            blocks_by_class[block.class_name].append(block)
        
        for class_name, blocks in blocks_by_class.items():
            # print(f"  - {class_name}: {len(blocks)} 个")
            # 统计识别的版面块
            if class_name.lower() in crop_counts:
                crop_counts[class_name.lower()] += len(blocks)
        
        # 保存版面块信息并切割特定类型的块（不保存页面图像）
        page_blocks_info = save_blocks_info_with_crops(
            page_result.blocks, 
            page_result.img, 
            output_dir, 
            page_result.page_idx
        )
        all_blocks_info.extend(page_blocks_info)
    
    # 打印版面块识别统计信息
    # total_blocks = sum(crop_counts.values())
    # if total_blocks > 0:
        # print(f"\n🎯 版面块识别统计:")
        # for block_type, count in crop_counts.items():
            # if count > 0:
                # print(f"  - {block_type}: {count} 个")
        # print(f"  - 总计: {total_blocks} 个关键版面块已识别并切割保存")
    # else:
        # print(f"\n未检测到 figure、isolate_formula 或 table 类型的块")
    
    # 可视化结果
    saved_paths = analyzer.visualize_result(result, output_dir, save_pdf=True)
    # print(f"\n结果已保存到: {output_dir}")
    for path in saved_paths:
        print(f"  - {path}")
    
    # 展示如何获取特定类型的块
    # title_blocks = result.get_blocks_by_class("title")
    # if title_blocks:
        # print(f"\n找到 {len(title_blocks)} 个标题块")
        # for block in title_blocks[:3]:  # 只显示前3个
            # print(f"  - 页码: {block.page_idx + 1}, 坐标: {block.box}, 置信度: {block.score:.2f}")
        # if len(title_blocks) > 3:
            # print(f"  - ... 等 {len(title_blocks) - 3} 个")
    
    # 保存所有块信息到json
    json_path = os.path.join(output_dir, "blocks_info.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_blocks_info, f, ensure_ascii=False, indent=2)
    # print(f"所有块信息已保存到: {json_path}")


def analyze_image_demo(image_path, output_dir, model_type, conf_thres, iou_thres, use_cuda):
    """图像版面分析演示"""
    # print(f"正在分析图像: {image_path}")
    
    # 清理输出目录
    clear_output_directory(output_dir)
    
    # 创建版面分析器
    analyzer = LayoutAnalyzer(
        model_type=model_type,
        conf_thres=conf_thres,
        iou_thres=iou_thres,
        use_cuda=use_cuda
    )
    
    # 分析图像
    result = analyzer.analyze_image(image_path)
    
    # 打印版面块信息并统计切割图像
    blocks_by_class = {}
    crop_counts = {"figure": 0, "isolate_formula": 0, "table": 0}  # 统计切割的图像数量
    
    for block in result.blocks:
        if block.class_name not in blocks_by_class:
            blocks_by_class[block.class_name] = []
        blocks_by_class[block.class_name].append(block)
    
    # print("\n版面块信息:")
    for class_name, blocks in blocks_by_class.items():
        # print(f"  - {class_name}: {len(blocks)} 个")
        # 统计切割的图像
        if class_name.lower() in crop_counts:
            crop_counts[class_name.lower()] += len(blocks)
    
    # 保存图像和版面块信息
    blocks_info = save_blocks_info_and_page_image(result.blocks, result.img, output_dir)
    
    # 打印切割统计信息
    total_crops = sum(crop_counts.values())
    if total_crops > 0:
        # print(f"\n🎯 切割图像统计:")
        for crop_type, count in crop_counts.items():
            if count > 0:
                print(f"  - {crop_type}: {count} 个")
        # print(f"  - 总计: {total_crops} 个图像已切割保存到 output/crops/ 文件夹")
    # else:
        # print(f"\n未检测到 figure、isolate_formula 或 table 类型的块")
    
    # 可视化结果
    saved_paths = analyzer.visualize_result(result, output_dir)
    # print(f"\n结果已保存到: {output_dir}")
    # for path in saved_paths:
        # print(f"  - {path}")
    
    # 保存所有块信息到json
    json_path = os.path.join(output_dir, "blocks_info.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(blocks_info, f, ensure_ascii=False, indent=2)
    # print(f"所有块信息已保存到: {json_path}")


def main():
    parser = argparse.ArgumentParser(description="版面分析器演示")
    parser.add_argument("--input", "-i", type=str, required=True, help="输入PDF文件或图像路径")
    parser.add_argument("--output", "-o", type=str, default="./layout_analyzer/output", help="输出目录")
    parser.add_argument("--model_type", "-m", type=str, default="doclayout_docstructbench", 
                       help="模型类型 (参考RapidLayout文档)")
    parser.add_argument("--conf_thres", "-c", type=float, default=0.25, help="置信度阈值")
    parser.add_argument("--iou_thres", type=float, default=0.5, help="IOU阈值")
    parser.add_argument("--use_cuda", action="store_true", help="是否使用CUDA加速")
    
    args = parser.parse_args()
    
    # 创建输出目录
    output_dir = Path(args.output)
    
    clear_output_directory(str(output_dir))
    
    # 根据输入类型执行相应的演示
    input_path = Path(args.input)
    if input_path.suffix.lower() == ".pdf":
        analyze_pdf_demo(
            input_path, 
            output_dir, 
            args.model_type, 
            args.conf_thres, 
            args.iou_thres, 
            args.use_cuda
        )
    elif input_path.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]:
        analyze_image_demo(
            input_path, 
            output_dir, 
            args.model_type, 
            args.conf_thres, 
            args.iou_thres, 
            args.use_cuda
        )
    else:
        print(f"不支持的文件类型: {input_path.suffix}")


if __name__ == "__main__":
    main()