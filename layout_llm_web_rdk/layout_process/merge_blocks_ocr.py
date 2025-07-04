#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本用于合并板块信息和OCR文本框信息
根据页面索引和坐标范围将OCR文本框分配到对应的板块中
"""

import json
import os


def check_bbox_overlap(block_bbox, text_bbox):
    """
    检查文本框是否在板块范围内
    
    Args:
        block_bbox: 板块边界框 [x1, y1, x2, y2]
        text_bbox: 文本框边界框 [x1, y1, x2, y2] 或 [x1, y1, x2, y2, ...]
    
    Returns:
        bool: 如果文本框在板块内返回True，否则返回False
    """
    # 确保text_bbox至少有4个坐标值
    if len(text_bbox) < 4:
        return False
    
    # 取前4个值作为边界框坐标
    text_x1, text_y1, text_x2, text_y2 = text_bbox[:4]
    block_x1, block_y1, block_x2, block_y2 = block_bbox
    
    # 计算文本框中心点
    text_center_x = (text_x1 + text_x2) / 2
    text_center_y = (text_y1 + text_y2) / 2
    
    # 检查中心点是否在板块内
    return (block_x1 <= text_center_x <= block_x2 and 
            block_y1 <= text_center_y <= block_y2)


def calculate_average_text_height(page_ocr_data, exclude_blocks=None):
    """
    计算页面中文本框的平均高度
    
    Args:
        page_ocr_data: 页面的OCR文本框数据
        exclude_blocks: 需要排除的块的边界框列表
    
    Returns:
        float: 平均文本高度
    """
    if exclude_blocks is None:
        exclude_blocks = []
    
    heights = []
    for text_box in page_ocr_data:
        text_bbox = text_box.get("bbox", [])
        if len(text_bbox) >= 4:
            # 检查是否在排除的块内
            is_excluded = False
            for exclude_bbox in exclude_blocks:
                if check_bbox_overlap(exclude_bbox, text_bbox):
                    is_excluded = True
                    break
            
            if not is_excluded:
                text_x1, text_y1, text_x2, text_y2 = text_bbox[:4]
                height = abs(text_y2 - text_y1)
                if height > 0:  # 确保高度有效
                    heights.append(height)
    
    # 如果没有有效的文本框，返回默认高度
    if not heights:
        return 20  # 默认高度
    
    return sum(heights) / len(heights)


def generate_virtual_text_boxes(block_bbox, avg_text_height, line_spacing_ratio=1.2):
    """
    为指定块生成虚拟文本框
    
    Args:
        block_bbox: 块的边界框 [x1, y1, x2, y2]
        avg_text_height: 平均文本高度
        line_spacing_ratio: 行间距比例
    
    Returns:
        list: 虚拟文本框列表
    """
    if len(block_bbox) < 4:
        return []
    
    block_x1, block_y1, block_x2, block_y2 = block_bbox
    block_width = block_x2 - block_x1
    block_height = block_y2 - block_y1
    
    if block_width <= 0 or block_height <= 0:
        return []
    
    # 计算行高（文本高度 + 行间距）
    line_height = avg_text_height * line_spacing_ratio
    
    # 计算可以放置的行数
    num_lines = max(1, int(block_height / line_height))
    
    virtual_text_boxes = []
    
    for i in range(num_lines):
        # 计算每行的y坐标
        y_start = block_y1 + i * line_height
        y_end = min(y_start + avg_text_height, block_y2)
        
        # 确保不超出块的边界
        if y_start >= block_y2:
            break
            
        virtual_text_box = {
            "illegibility": False,
            "bbox": [block_x1, y_start, block_x2, y_end],
            "score": 1.0,
            "transcription": "",  # 空文本
            "is_virtual": True  # 标记为虚拟文本框
        }
        virtual_text_boxes.append(virtual_text_box)
    
    return virtual_text_boxes


def merge_blocks_and_ocr(blocks_file, ocr_file, output_file):
    """
    合并板块信息和OCR结果
    
    Args:
        blocks_file: 板块信息文件路径
        ocr_file: OCR结果文件路径
        output_file: 输出文件路径
    """
    
    # 读取板块信息
    with open(blocks_file, 'r', encoding='utf-8') as f:
        blocks_data = json.load(f)
    
    # 读取OCR结果
    with open(ocr_file, 'r', encoding='utf-8') as f:
        ocr_data = json.load(f)
    
    # 按页面组织板块信息
    blocks_by_page = {}
    for block in blocks_data:
        page_idx = block.get('page_idx', 0)
        if page_idx not in blocks_by_page:
            blocks_by_page[page_idx] = []
        blocks_by_page[page_idx].append(block)
    
    # 按页面组织OCR文本框信息
    ocr_by_page = {}
    for text_box in ocr_data:
        page_idx = text_box.get('page_idx', 0)
        if page_idx not in ocr_by_page:
            ocr_by_page[page_idx] = []
        ocr_by_page[page_idx].append(text_box)
    
    # 创建合并后的结果结构
    merged_result = {}
    
    # 遍历每个页面
    for page_idx, page_blocks in blocks_by_page.items():
        page_key = f"page{page_idx}"
        
        # 获取对应页面的OCR文本框
        page_ocr_data = ocr_by_page.get(page_idx, [])
        
        # 找出需要特殊处理的块类型
        special_block_types = {"figure", "table", "isolate_formula"}
        special_blocks_bboxes = []
        
        # 预过滤置信度低于0.5的块和abandon类型的块，用于计算统计信息
        filtered_blocks = [
            block for block in page_blocks 
            if block.get("score", 0.0) >= 0.5 and block.get("class_name", "").lower() != "abandon"
        ]
        
        for block in filtered_blocks:
            if block.get("class_name", "").lower() in special_block_types:
                block_bbox = block.get("bbox", [])
                if len(block_bbox) >= 4:
                    special_blocks_bboxes.append(block_bbox)
        
        # 计算页面中其他文本框的平均高度（排除特殊块内的文本框）
        avg_text_height = calculate_average_text_height(page_ocr_data, special_blocks_bboxes)
        
        # 计算统计信息
        total_original_blocks = len(page_blocks)
        low_score_blocks = len([b for b in page_blocks if b.get("score", 0.0) < 0.5])
        abandon_blocks = len([b for b in page_blocks if b.get("class_name", "").lower() == "abandon"])
        valid_blocks_count = len(filtered_blocks)
        
        # 为当前页面创建结果结构
        merged_result[page_key] = {
            "page_info": {
                "page_index": page_idx,
                "total_original_blocks": total_original_blocks,
                "valid_blocks": valid_blocks_count,
                "filtered_low_score_blocks": low_score_blocks,
                "filtered_abandon_blocks": abandon_blocks,
                "total_text_boxes": len(page_ocr_data),
                "avg_text_height": avg_text_height
            },
            "blocks": []
        }
        
        # 遍历当前页面的每个板块
        for block in page_blocks:
            # 过滤置信度低于0.5的块
            block_score = block.get("score", 0.0)
            if block_score < 0.5:
                continue  # 跳过置信度低于0.5的块
            
            # 过滤abandon类型的块
            block_class_name = block.get("class_name", "").lower()
            if block_class_name == "abandon":
                continue  # 跳过abandon类型的块
            
            block_info = {
                "block_info": {
                    "class_name": block.get("class_name", ""),
                    "bbox": block.get("bbox", []),
                    "score": block.get("score", 0.0),
                    "block_idx": block.get("block_idx", -1),
                    "page_idx": block.get("page_idx", 0)
                },
                "contained_text_boxes": []
            }
            
            # 如果是figure、table、isolate_formula类型，且有切割图像路径，则保留该信息
            if block.get("crop_image_path"):
                block_info["block_info"]["crop_image_path"] = block.get("crop_image_path")
            
            # 检查是否是需要特殊处理的块类型
            if block_class_name in special_block_types:
                # 对于特殊块类型，生成虚拟文本框而不是匹配真实文本框
                block_bbox = block.get("bbox", [])
                virtual_text_boxes = generate_virtual_text_boxes(block_bbox, avg_text_height)
                block_info["contained_text_boxes"] = virtual_text_boxes
                block_info["block_info"]["is_virtual_text"] = True
            else:
                # 对于普通块，正常匹配文本框
                for text_box in page_ocr_data:
                    text_bbox = text_box.get("bbox", [])
                    block_bbox = block.get("bbox", [])
                    
                    # 检查文本框是否在板块范围内
                    if check_bbox_overlap(block_bbox, text_bbox):
                        text_info = {
                            "illegibility": text_box.get("illegibility", False),
                            "bbox": text_bbox,
                            "score": text_box.get("score", 0.0),
                            "transcription": text_box.get("text", ""),  # OCR文件中使用"text"字段
                            "is_virtual": False
                        }
                        block_info["contained_text_boxes"].append(text_info)
                
                block_info["block_info"]["is_virtual_text"] = False
            
            # 添加统计信息
            block_info["block_info"]["contained_text_count"] = len(block_info["contained_text_boxes"])
            
            merged_result[page_key]["blocks"].append(block_info)
        
    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_result, f, ensure_ascii=False, indent=2)
    
    # print(f"合并完成！结果已保存到: {output_file}")
    
    # 打印统计信息
    total_original_blocks = sum(page_data["page_info"].get("total_original_blocks", 0) for page_data in merged_result.values())
    total_valid_blocks = sum(len(page_data["blocks"]) for page_data in merged_result.values())
    total_low_score_filtered = sum(page_data["page_info"].get("filtered_low_score_blocks", 0) for page_data in merged_result.values())
    total_abandon_filtered = sum(page_data["page_info"].get("filtered_abandon_blocks", 0) for page_data in merged_result.values())
    total_text_boxes = sum(
        sum(len(block["contained_text_boxes"]) for block in page_data["blocks"])
        for page_data in merged_result.values()
    )
    
    # print(f"统计信息:")
    # print(f"- 总页面数: {len(merged_result)}")
    # print(f"- 原始板块总数: {total_original_blocks}")
    # print(f"- 有效板块数: {total_valid_blocks}")
    # print(f"- 过滤的低置信度块数: {total_low_score_filtered} (置信度 < 0.5)")
    # print(f"- 过滤的abandon类型块数: {total_abandon_filtered}")
    # print(f"- 匹配的文本框数: {total_text_boxes}")


def main():
    """主函数"""
    # 文件路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    blocks_file = os.path.join(current_dir, "layout_analyzer/output/blocks_info.json")
    ocr_file = os.path.join(current_dir, "ppocr/results/ppocr_flat_bbox4.json")
    output_file = os.path.join(current_dir, "merged_blocks_ocr_result.json")
    
    # 检查输入文件是否存在
    if not os.path.exists(blocks_file):
        print(f"错误: 板块信息文件不存在: {blocks_file}")
        return
    
    if not os.path.exists(ocr_file):
        print(f"错误: OCR结果文件不存在: {ocr_file}")
        return
    
    print("开始合并板块信息和OCR结果...")
    print(f"板块信息文件: {blocks_file}")
    print(f"OCR结果文件: {ocr_file}")
    print(f"输出文件: {output_file}")
    
    try:
        merge_blocks_and_ocr(blocks_file, ocr_file, output_file)
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
