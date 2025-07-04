#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将textboxes_with_reading_order.json中的内容按照阅读顺序转换为Markdown格式
输出文档的实际内容，便于阅读
"""

import os
import json
from pathlib import Path

def extract_text_from_textbox(textbox):
    """从文本框中提取文本内容"""
    transcription = textbox.get("transcription", "").strip()
    is_virtual = textbox.get("is_virtual", False)
    
    if is_virtual:
        return ""  # 虚拟文本框没有实际文本内容
    
    return transcription

def get_block_type_markdown_prefix(class_name, level=1):
    """根据块类型返回相应的Markdown前缀"""
    class_name = class_name.lower()
    
    if "title" in class_name:
        return "#" * min(level + 1, 6) + " "  # 标题用##, ###等
    elif "figure_caption" in class_name:
        return "*图注: "
    elif "table_caption" in class_name:
        return "*表注: "
    elif class_name in ["figure", "table", "isolate_formula"]:
        return f"**[{class_name.upper()}]**\n\n"
    else:
        return ""  # 普通文本不加前缀

def get_block_type_markdown_suffix(class_name):
    """根据块类型返回相应的Markdown后缀"""
    class_name = class_name.lower()
    
    if "figure_caption" in class_name or "table_caption" in class_name:
        return "*"
    else:
        return ""

def convert_json_to_markdown(json_file, output_file):
    """将JSON内容转换为Markdown格式"""
    
    # 读取JSON数据
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    markdown_content = []
    
    # 添加文档标题
    markdown_content.append("# 文档内容\n")
    # markdown_content.append(f"*从 {os.path.basename(json_file)} 提取*\n\n")
    
    # 按页面顺序处理
    for page_data in data["pages"]:
        page_idx = page_data["page_index"]
        
        # 添加页面标题
        markdown_content.append(f"## 第 {page_idx + 1} 页\n")
        
        # 按照页面内块的顺序处理（已经按中位数排序）
        blocks = page_data["blocks"]
        
        for block in blocks:
            block_info = block.get("block_info", {})
            class_name = block_info.get("class_name", "unknown")
            
            # 跳过abandon类型的块
            if class_name.lower() == "abandon":
                continue
            
            # 收集块内所有文本框的内容
            textbox_contents = []
            
            # 获取块内文本框，按阅读顺序排序
            textboxes = block.get("contained_text_boxes", [])
            
            # 按页面阅读顺序排序文本框
            sorted_textboxes = sorted(
                [tb for tb in textboxes if tb.get("page_reading_order", -1) >= 0],
                key=lambda x: x.get("page_reading_order", float('inf'))
            )
            
            # 提取文本内容
            for textbox in sorted_textboxes:
                text = extract_text_from_textbox(textbox)
                if text:
                    textbox_contents.append(text)
            
            # 如果块有文本内容，则添加到Markdown
            if textbox_contents:
                # 添加块类型前缀
                title_level = 2 if "title" in class_name.lower() else 3
                prefix = get_block_type_markdown_prefix(class_name, title_level)
                suffix = get_block_type_markdown_suffix(class_name)
                
                # 合并文本内容
                if class_name.lower() in ["figure", "table", "isolate_formula"]:
                    # 对于图表等特殊块，显示图片
                    crop_path = block_info.get("crop_image_path", "")
                    if crop_path:
                        # 使用Markdown图片语法显示图片，不显示路径文本
                        image_name = os.path.basename(crop_path)
                        markdown_content.append(f"![{class_name.upper()}: {image_name}]({crop_path})\n\n")
                    else:
                        markdown_content.append(f"{prefix}\n")
                elif "title" in class_name.lower():
                    # 标题块
                    title_text = " ".join(textbox_contents)
                    markdown_content.append(f"{prefix}{title_text}\n")
                else:
                    # 普通文本块
                    if prefix:
                        markdown_content.append(prefix)
                    
                    # 将文本框内容连接成段落
                    paragraph = " ".join(textbox_contents)
                    markdown_content.append(f"{paragraph}{suffix}\n")
                
                markdown_content.append("\n")  # 块之间添加空行
            
            elif class_name.lower() in ["figure", "table", "isolate_formula"]:
                # 即使没有文本，也显示特殊块的图片
                prefix = get_block_type_markdown_prefix(class_name)
                crop_path = block_info.get("crop_image_path", "")
                if crop_path:
                    # 使用Markdown图片语法显示图片，不显示路径文本
                    image_name = os.path.basename(crop_path)
                    markdown_content.append(f"![{class_name.upper()}: {image_name}]({crop_path})\n\n")
                else:
                    markdown_content.append(f"{prefix}\n")
        
        markdown_content.append("\n---\n\n")  # 页面之间添加分隔线
    
    # 写入Markdown文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(markdown_content)
    
    # print(f"Markdown内容已保存到: {output_file}")
    
    # 统计信息
    total_lines = len(markdown_content)
    total_pages = len(data["pages"])
    total_blocks = sum(len(page["blocks"]) for page in data["pages"])
    
    # print(f"\n转换统计:")
    # print(f"- 总页数: {total_pages}")
    # print(f"- 总块数: {total_blocks}")
    # print(f"- Markdown行数: {total_lines}")

def convert_with_detailed_structure(json_file, output_file):
    """生成带详细结构信息的Markdown"""
    
    # 读取JSON数据
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    markdown_content = []
    
    # 添加文档标题和目录
    markdown_content.append("# 文档内容（详细结构）\n")
    # markdown_content.append(f"*从 {os.path.basename(json_file)} 提取*\n\n")
    
    # 生成目录
    markdown_content.append("## 目录\n\n")
    for page_data in data["pages"]:
        page_idx = page_data["page_index"]
        markdown_content.append(f"- [第 {page_idx + 1} 页](#第-{page_idx + 1}-页)\n")
    markdown_content.append("\n---\n\n")
    
    # 按页面顺序处理
    for page_data in data["pages"]:
        page_idx = page_data["page_index"]
        page_info = page_data["page_info"]
        
        # 添加页面标题和统计信息
        markdown_content.append(f"## 第 {page_idx + 1} 页\n")
        markdown_content.append(f"*块数: {page_info['total_blocks']}, ")
        markdown_content.append(f"文本框数: {page_info['total_textboxes']}, ")
        markdown_content.append(f"虚拟文本框: {page_info['virtual_textboxes']}*\n\n")
        
        # 按照页面内块的顺序处理
        blocks = page_data["blocks"]
        
        for block_idx, block in enumerate(blocks):
            block_info = block.get("block_info", {})
            class_name = block_info.get("class_name", "unknown")
            page_block_order = block_info.get("page_block_order", -1)
            median_order = block_info.get("textbox_reading_order_median", -1)
            
            # 跳过abandon类型的块
            if class_name.lower() == "abandon":
                continue
            
            # 添加块标题
            markdown_content.append(f"### 块 {page_block_order} - {class_name}\n")
            markdown_content.append(f"*中位数阅读顺序: {median_order}, ")
            markdown_content.append(f"文本框数: {block_info.get('contained_text_count', 0)}*\n\n")
            
            # 处理特殊块类型
            if class_name.lower() in ["figure", "table", "isolate_formula"]:
                crop_path = block_info.get("crop_image_path", "")
                if crop_path:
                    # 使用Markdown图片语法显示图片，不显示路径文本
                    image_name = os.path.basename(crop_path)
                    markdown_content.append(f"**[{class_name.upper()}]**\n\n")
                    markdown_content.append(f"![{class_name.upper()}: {image_name}]({crop_path})\n\n")
                else:
                    markdown_content.append(f"**[{class_name.upper()}]** *(无切割图像)*\n\n")
                
                # 显示虚拟文本框信息
                is_virtual = block_info.get("is_virtual_text", False)
                if is_virtual:
                    textboxes = block.get("contained_text_boxes", [])
                    markdown_content.append(f"*包含 {len(textboxes)} 个虚拟文本框*\n\n")
            else:
                # 处理文本内容
                textboxes = block.get("contained_text_boxes", [])
                
                # 按页面阅读顺序排序文本框
                sorted_textboxes = sorted(
                    [tb for tb in textboxes if tb.get("page_reading_order", -1) >= 0],
                    key=lambda x: x.get("page_reading_order", float('inf'))
                )
                
                # 提取并显示文本内容
                text_contents = []
                for textbox in sorted_textboxes:
                    text = extract_text_from_textbox(textbox)
                    if text:
                        text_contents.append(text)
                
                if text_contents:
                    if "title" in class_name.lower():
                        # 标题格式
                        title_text = " ".join(text_contents)
                        markdown_content.append(f"**{title_text}**\n\n")
                    else:
                        # 普通文本格式
                        paragraph = " ".join(text_contents)
                        markdown_content.append(f"{paragraph}\n\n")
                else:
                    markdown_content.append("*（无文本内容）*\n\n")
            
            markdown_content.append("---\n\n")  # 块之间添加分隔线
        
        markdown_content.append("\n\n")  # 页面之间添加空行
    
    # 写入Markdown文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(markdown_content)
    
    # print(f"详细结构Markdown已保存到: {output_file}")

def main():
    """主函数"""
    # 配置路径
    json_file = "/home/m/Documents/office-AI/layout/textboxes_with_reading_order.json"
    simple_output = "/home/m/Documents/office-AI/layout/document_content.md"
    detailed_output = "/home/m/Documents/office-AI/layout/document_content_detailed.md"
    
    # 检查输入文件
    if not os.path.exists(json_file):
        print(f"错误: JSON文件不存在 {json_file}")
        return
    
    print("=== JSON to Markdown 转换器 ===")
    print(f"输入文件: {json_file}")
    print(f"简化输出: {simple_output}")
    print(f"详细输出: {detailed_output}")
    
    try:
        # 生成简化版Markdown（只包含内容）
        print("\n生成简化版Markdown...")
        convert_json_to_markdown(json_file, simple_output)
        
        # 生成详细版Markdown（包含结构信息）
        print("\n生成详细版Markdown...")
        convert_with_detailed_structure(json_file, detailed_output)
        
        print("\n=== 转换完成 ===")
        print("已生成两个版本的Markdown文件:")
        print(f"1. 简化版（纯内容）: {simple_output}")
        print(f"2. 详细版（含结构）: {detailed_output}")
        
    except Exception as e:
        print(f"处理过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
