#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对merged_blocks_ocr_result.json中的文本框级别进行阅读顺序排序
基于LayoutReader模型为每个文本框添加阅读顺序信息
同时计算每个块的文本框阅读顺序中位数，并按页码和中位数重新排序
"""

import os
import sys
import json
import torch
import statistics
from pathlib import Path
from transformers import LayoutLMv3ForTokenClassification
from collections import defaultdict

# ==== 以下为 helpers.py 关键函数 ==== #
MAX_LEN = 510
CLS_TOKEN_ID = 0
UNK_TOKEN_ID = 3
EOS_TOKEN_ID = 2

def boxes2inputs(boxes):
    bbox = [[0, 0, 0, 0]] + boxes + [[0, 0, 0, 0]]
    input_ids = [CLS_TOKEN_ID] + [UNK_TOKEN_ID] * len(boxes) + [EOS_TOKEN_ID]
    attention_mask = [1] + [1] * len(boxes) + [1]
    return {
        "bbox": torch.tensor([bbox]),
        "attention_mask": torch.tensor([attention_mask]),
        "input_ids": torch.tensor([input_ids]),
    }

def prepare_inputs(inputs, model):
    ret = {}
    for k, v in inputs.items():
        v = v.to(model.device)
        if torch.is_floating_point(v):
            v = v.to(model.dtype)
        ret[k] = v
    return ret

def parse_logits(logits, length):
    logits = logits[1 : length + 1, :length]
    orders = logits.argsort(descending=False).tolist()
    ret = [o.pop() for o in orders]
    while True:
        order_to_idxes = defaultdict(list)
        for idx, order in enumerate(ret):
            order_to_idxes[order].append(idx)
        order_to_idxes = {k: v for k, v in order_to_idxes.items() if len(v) > 1}
        if not order_to_idxes:
            break
        for order, idxes in order_to_idxes.items():
            idxes_to_logit = {}
            for idx in idxes:
                idxes_to_logit[idx] = logits[idx, order]
            idxes_to_logit = sorted(
                idxes_to_logit.items(), key=lambda x: x[1], reverse=True
            )
            for idx, _ in idxes_to_logit[1:]:
                ret[idx] = orders[idx].pop()
    return ret
# ==== helpers.py 关键函数结束 ====

def calculate_median(numbers):
    """计算数字列表的中位数"""
    if not numbers:
        return float('inf')  # 如果没有数字，返回无穷大，让它排在最后
    return statistics.median(numbers)

def process_textboxes_reading_order(input_json_path, output_json_path, model_path=None):
    """
    处理合并后的JSON文件，为文本框添加阅读顺序信息
    
    Args:
        input_json_path: 输入JSON文件路径 (merged_blocks_ocr_result.json)
        output_json_path: 输出JSON文件路径
        model_path: 模型路径（如果为None，使用默认路径）
    """
    
    # 加载模型
    print("加载LayoutReader模型...")
    if model_path is None:
        model_path = "/home/m/.cache/modelscope/hub/models/ppaanngggg/layoutreader"
    
    model = LayoutLMv3ForTokenClassification.from_pretrained(model_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    model = model.to(device)
    model.eval()
    
    # 读取JSON文件
    print(f"读取JSON文件: {input_json_path}")
    with open(input_json_path, 'r', encoding='utf-8') as f:
        merged_data = json.load(f)
    
    # 创建输出结构
    output_data = {}
    global_textbox_order = 0  # 全局文本框阅读顺序计数器
    
    # 按页码顺序处理每个页面 - 使用page_index排序而不是字符串排序
    page_items = [(page_key, page_data) for page_key, page_data in merged_data.items()]
    page_items.sort(key=lambda x: x[1]["page_info"]["page_index"])
    
    # 处理每个页面
    for page_key, page_data in page_items:
        page_idx = page_data["page_info"]["page_index"]
        
        print(f"\n处理 {page_key} (第{page_idx+1}页)")
        
        # 收集页面中所有的文本框（包括虚拟文本框）
        all_textboxes = []
        textbox_metadata = []  # 存储文本框的元数据（块索引、文本框在块中的索引）
        
        for block_idx, block in enumerate(page_data["blocks"]):
            for textbox_idx_in_block, textbox in enumerate(block["contained_text_boxes"]):
                # 处理所有文本框（包括虚拟文本框）
                bbox = textbox.get("bbox", [])
                if len(bbox) >= 4:
                    all_textboxes.append(textbox)
                    textbox_metadata.append({
                        "block_idx": block_idx,
                        "textbox_idx_in_block": textbox_idx_in_block,
                        "original_textbox": textbox,
                        "is_virtual": textbox.get("is_virtual", False)
                    })
        
        # print(f"页面中共有 {len(all_textboxes)} 个文本框（包括虚拟文本框）")
        
        # 如果没有文本框，跳过
        if not all_textboxes:
            output_data[page_key] = page_data.copy()
            continue
        
        # 提取bbox并归一化
        boxes = []
        for textbox in all_textboxes:
            bbox = textbox["bbox"]
            x1, y1, x2, y2 = bbox[:4]
            
            # 归一化坐标到0-1000范围 (假设页面尺寸为1700x2200)
            x1 = min(1000, max(0, int(x1 * 1000 / 1700)))
            y1 = min(1000, max(0, int(y1 * 1000 / 2200)))
            x2 = min(1000, max(0, int(x2 * 1000 / 1700)))
            y2 = min(1000, max(0, int(y2 * 1000 / 2200)))
            boxes.append([x1, y1, x2, y2])
        
        # 使用模型推理阅读顺序
        inputs = boxes2inputs(boxes)
        inputs = prepare_inputs(inputs, model)
        
        with torch.no_grad():
            logits = model(**inputs).logits.cpu().squeeze(0)
        
        # 解析阅读顺序
        orders = parse_logits(logits, len(boxes))
        # print(f"文本框阅读顺序: {orders}")
        
        # 创建阅读顺序映射 - 从原始文本框索引到阅读顺序的映射
        reading_order_map = {}
        for reading_order, original_textbox_idx in enumerate(orders):
            if 0 <= original_textbox_idx < len(textbox_metadata):
                metadata = textbox_metadata[original_textbox_idx]
                key = (metadata["block_idx"], metadata["textbox_idx_in_block"])
                reading_order_map[key] = {
                    "page_reading_order": reading_order,
                    "global_reading_order": global_textbox_order
                }
                global_textbox_order += 1
        
        # 创建输出页面数据
        output_page_data = {
            "page_info": page_data["page_info"].copy(),
            "blocks": []
        }
        
        # 添加文本框统计信息
        virtual_count = sum(1 for textbox in all_textboxes if textbox.get("is_virtual", False))
        real_count = len(all_textboxes) - virtual_count
        output_page_data["page_info"]["total_textboxes"] = len(all_textboxes)
        output_page_data["page_info"]["virtual_textboxes"] = virtual_count
        output_page_data["page_info"]["real_textboxes"] = real_count
        
        # 处理每个块
        for block_idx, block in enumerate(page_data["blocks"]):
            output_block = {
                "block_info": block["block_info"].copy(),
                "contained_text_boxes": []
            }
            
            # 收集该块中非虚拟文本框的阅读顺序
            block_reading_orders = []
            
            # 处理块中的文本框
            for textbox_idx_in_block, textbox in enumerate(block["contained_text_boxes"]):
                output_textbox = textbox.copy()
                
                # 为所有文本框（包括虚拟文本框）添加阅读顺序信息
                key = (block_idx, textbox_idx_in_block)
                if key in reading_order_map:
                    reading_info = reading_order_map[key]
                    output_textbox["page_reading_order"] = reading_info["page_reading_order"]
                    output_textbox["global_reading_order"] = reading_info["global_reading_order"]
                    block_reading_orders.append(reading_info["page_reading_order"])
                    
                    # 添加文本框类型标识
                    # if textbox.get("is_virtual", False):
                    #     print(f"  虚拟文本框 块{block_idx}-文本框{textbox_idx_in_block}: 页面顺序={reading_info['page_reading_order']}, 全局顺序={reading_info['global_reading_order']}")
                    # else:
                    #     print(f"  真实文本框 块{block_idx}-文本框{textbox_idx_in_block}: 页面顺序={reading_info['page_reading_order']}, 全局顺序={reading_info['global_reading_order']}")
                else:
                    # 如果没有找到阅读顺序信息，设置为-1
                    output_textbox["page_reading_order"] = -1
                    output_textbox["global_reading_order"] = -1
                
                output_block["contained_text_boxes"].append(output_textbox)
            
            # 计算块的阅读顺序中位数
            block_median_order = calculate_median(block_reading_orders)
            output_block["block_info"]["textbox_reading_order_median"] = block_median_order
            output_block["block_info"]["textbox_count_for_median"] = len(block_reading_orders)
            
            output_page_data["blocks"].append(output_block)
        
        # 按块的中位数阅读顺序对块进行排序
        output_page_data["blocks"].sort(key=lambda block: block["block_info"]["textbox_reading_order_median"])
        
        output_data[page_key] = output_page_data
        
        # 打印页面处理结果
        # print(f"页面 {page_idx+1} 处理完成，共 {len(all_textboxes)} 个文本框已排序")
        # print(f"块按中位数阅读顺序重新排列")
    
    # 创建最终的有序输出结构：按页码和块的中位数顺序
    final_output = {
        "metadata": {
            "total_pages": len(output_data),
            "total_textboxes": sum(
                page_data["page_info"].get("total_non_virtual_textboxes", 0)
                for page_data in output_data.values()
            ),
            "processing_info": "blocks_ordered_by_textbox_median_reading_order"
        },
        "pages": []
    }
    
    # 按页码顺序处理每个页面
    page_items = [(page_key, page_data) for page_key, page_data in output_data.items()]
    page_items.sort(key=lambda x: x[1]["page_info"]["page_index"])
    
    for page_key, page_data in page_items:
        page_data = output_data[page_key]
        page_idx = page_data["page_info"]["page_index"]
        
        page_output = {
            "page_index": page_idx,
            "page_info": page_data["page_info"],
            "blocks": []
        }
        
        # 块已经按中位数排序了，直接添加
        for block_idx, block in enumerate(page_data["blocks"]):
            block_output = block.copy()
            # 添加在页面中的新顺序
            block_output["block_info"]["page_block_order"] = block_idx
            page_output["blocks"].append(block_output)
        
        final_output["pages"].append(page_output)
    
    # 保存处理后的结果
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    # print(f"\n处理完成！结果已保存到: {output_json_path}")
    
    # 生成统计信息
    # total_textboxes = final_output["metadata"]["total_textboxes"]
    # print(f"总共处理了 {total_textboxes} 个文本框")
    print(f"总共 {final_output['metadata']['total_pages']} 个页面")
    
    return final_output

def create_textbox_reading_order_report(output_data, report_path):
    """创建文本框阅读顺序报告"""
    report_lines = []
    report_lines.append("# 文本框阅读顺序分析报告\n")
    report_lines.append(f"生成时间: {__import__('datetime').datetime.now()}\n")
    report_lines.append(f"总页面数: {output_data['metadata']['total_pages']}\n")
    report_lines.append(f"总文本框数: {output_data['metadata']['total_textboxes']}\n")
    report_lines.append(f"处理说明: 块已按文本框阅读顺序中位数重新排序\n\n")
    
    # 处理每个页面
    for page in output_data["pages"]:
        page_idx = page["page_index"]
        page_textboxes = page["page_info"].get("total_non_virtual_textboxes", 0)
        
        report_lines.append(f"## 第 {page_idx + 1} 页 - {page_textboxes} 个文本框\n\n")
        
        # 处理每个块
        for block_order, block in enumerate(page["blocks"]):
            block_class = block["block_info"].get("class_name", "unknown")
            block_median = block["block_info"].get("textbox_reading_order_median", "N/A")
            textbox_count = block["block_info"].get("textbox_count_for_median", 0)
            
            if block_median == float('inf'):
                median_str = "无文本框"
            else:
                median_str = f"{block_median:.1f}"
            
            report_lines.append(f"### 块 {block_order + 1}: [{block_class}] (中位数: {median_str}, 文本框数: {textbox_count})\n\n")
            
            # 收集块中的非虚拟文本框并按阅读顺序排序
            block_textboxes = []
            for textbox in block["contained_text_boxes"]:
                if not textbox.get("is_virtual", False):
                    page_reading_order = textbox.get("page_reading_order", -1)
                    global_reading_order = textbox.get("global_reading_order", -1)
                    transcription = textbox.get("transcription", "")
                    bbox = textbox.get("bbox", [])
                    
                    block_textboxes.append({
                        "page_reading_order": page_reading_order,
                        "global_reading_order": global_reading_order,
                        "transcription": transcription,
                        "bbox": bbox
                    })
            
            # 按页面阅读顺序排序
            block_textboxes.sort(key=lambda x: x["page_reading_order"])
            
            for textbox in block_textboxes:
                text_preview = textbox["transcription"][:60] + "..." if len(textbox["transcription"]) > 60 else textbox["transcription"]
                bbox_str = f"[{', '.join(map(str, textbox['bbox'][:4]))}]" if textbox['bbox'] else "[]"
                
                report_lines.append(
                    f"  {textbox['page_reading_order'] + 1:2d}. [全局:{textbox['global_reading_order']:3d}] {text_preview}\n"
                    f"      位置: {bbox_str}\n"
                )
            
            report_lines.append("\n")
    
    # 保存报告
    with open(report_path, 'w', encoding='utf-8') as f:
        f.writelines(report_lines)
    
    print(f"文本框阅读顺序报告已保存到: {report_path}")

def main():
    """主函数"""
    # 配置路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_json = os.path.join(current_dir, "merged_blocks_ocr_result.json")
    output_json = os.path.join(current_dir, "textboxes_with_reading_order.json")
    report_path = os.path.join(current_dir, "textbox_reading_order_report.md")
    
    # 检查输入文件
    if not os.path.exists(input_json):
        print(f"错误: 输入文件不存在 {input_json}")
        return
    
    try:
        # 处理JSON文件
        output_data = process_textboxes_reading_order(input_json, output_json)
        
        # 生成报告
        create_textbox_reading_order_report(output_data, report_path)
        
        print("\n=== 处理完成 ===")
        print(f"输入文件: {input_json}")
        print(f"输出文件: {output_json}")
        print(f"报告文件: {report_path}")
        
    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
