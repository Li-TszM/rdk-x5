#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF文档处理完整流水线
整合版面分析、OCR识别、文本排序和Markdown生成的完整流程
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
import re
import cv2
import time
from datetime import timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加模块路径
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# 尝试导入各个模块，如果失败提供错误信息
try:
    from layout_analyzer.layout_analyzer import LayoutAnalyzer
    from layout_analyzer.demo_analyzer import save_blocks_info_only, save_blocks_info_with_crops
except ImportError as e:
    print(f"警告: 无法导入LayoutAnalyzer或demo_analyzer: {e}")
    LayoutAnalyzer = None
    save_blocks_info_only = None
    save_blocks_info_with_crops = None

try:
    from ppocr.convert_points_to_bbox import convert_to_flat_format
except ImportError as e:
    print(f"警告: 无法导入convert_to_flat_format: {e}")
    convert_to_flat_format = None

try:
    from merge_blocks_ocr import merge_blocks_and_ocr
except ImportError as e:
    print(f"警告: 无法导入merge_blocks_and_ocr: {e}")
    merge_blocks_and_ocr = None

try:
    from textbox_reading_order import process_textboxes_reading_order
except ImportError as e:
    print(f"警告: 无法导入process_textboxes_reading_order: {e}")
    process_textboxes_reading_order = None

try:
    from json_to_markdown_content import convert_json_to_markdown
except ImportError as e:
    print(f"警告: 无法导入convert_json_to_markdown: {e}")
    convert_json_to_markdown = None


class DocumentProcessingPipeline:
    """文档处理流水线"""
    
    def __init__(self, input_pdf_path, output_base_dir="results"):
        """
        初始化流水线
        
        Args:
            input_pdf_path: 输入PDF文件路径
            output_base_dir: 输出基础目录
        """
        self.input_pdf_path = Path(input_pdf_path)
        self.output_base_dir = Path(output_base_dir)
        
        # 生成输出目录（基于输入文件名）
        self.pdf_name = self.input_pdf_path.stem
        self.output_dir = self.output_base_dir / self.pdf_name
        
        # 创建临时文件目录
        self.temp_dir = self.output_dir / "temp"
        self.images_dir = self.output_dir / "images"
        
        # 各阶段输出文件路径
        self.layout_output_dir = self.temp_dir / "layout_output"
        self.blocks_info_file = self.temp_dir / f"{self.pdf_name}_blocks_info.json"
        self.ppocr_output_file = self.temp_dir / f"{self.pdf_name}_ppocr_results.json"
        self.ppocr_bbox_file = self.temp_dir / f"{self.pdf_name}_ppocr_bbox.json"
        self.merged_file = self.temp_dir / f"{self.pdf_name}_merged.json"
        self.sorted_file = self.temp_dir / f"{self.pdf_name}_sorted.json"
        self.final_markdown = self.output_dir / f"{self.pdf_name}.md"
        
        # 计时相关变量
        self.timing_results = {}
        self.pipeline_start_time = None
        
        # 创建必要的目录
        self._create_directories()
    
    def _format_duration(self, seconds):
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.2f}秒"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}分{remaining_seconds:.2f}秒"
    
    def _create_directories(self):
        """创建必要的目录"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.layout_output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 初始化工作目录完成")
    
    def _format_duration(self, seconds):
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.2f}秒"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            return f"{minutes}分{remaining_seconds:.2f}秒"
    
    def _print_timing_info(self, step_name, duration):
        """打印计时信息"""
        formatted_time = self._format_duration(duration)
        print(f"⏱️  {step_name} 耗时: {formatted_time}")
        self.timing_results[step_name] = duration
    
    def step1_layout_analysis(self):
        """步骤1: 版面分析"""
        print("=" * 60)
        print("步骤1: 开始版面分析...")
        step_start_time = time.time()
        
        if LayoutAnalyzer is None:
            print("错误: LayoutAnalyzer模块未正确导入")
            return False
        
        try:
            # 创建版面分析器
            analyzer = LayoutAnalyzer(
                model_type="doclayout_docstructbench",
                conf_thres=0.25,
                iou_thres=0.5,
                use_cuda=False  # 先用CPU模式确保兼容性
            )
            
            # 分析PDF
            result = analyzer.analyze_pdf(str(self.input_pdf_path))
            
            # 保存可视化结果
            saved_paths = analyzer.visualize_result(
                result, 
                str(self.layout_output_dir), 
                save_pdf=True
            )
            
            # 保存blocks信息并切割特定类型的块（不保存完整页面图像）
            all_blocks_info = []
            crop_counts = {"figure": 0, "isolate_formula": 0, "table": 0}
            
            for page_result in result.page_results:
                # 使用新的函数保存版面块信息并切割特定类型的块
                page_blocks_info = save_blocks_info_with_crops(
                    page_result.blocks, 
                    page_result.img, 
                    str(self.layout_output_dir), 
                    page_result.page_idx
                )
                all_blocks_info.extend(page_blocks_info)
                
                # 统计切割的块数量
                for block in page_result.blocks:
                    if block.class_name.lower() in crop_counts:
                        crop_counts[block.class_name.lower()] += 1
            
            # 打印切割统计信息
            total_crops = sum(crop_counts.values())
            if total_crops > 0:
                print(f"🎯 版面块切割统计:")
                for block_type, count in crop_counts.items():
                    if count > 0:
                        print(f"  - {block_type}: {count} 个")
                print(f"  - 总计: {total_crops} 个关键版面块已切割保存")
            
            # 保存blocks信息到JSON文件
            with open(self.blocks_info_file, "w", encoding="utf-8") as f:
                json.dump(all_blocks_info, f, ensure_ascii=False, indent=2)
            
            step_duration = time.time() - step_start_time
            self._print_timing_info("版面分析", step_duration)
            
            print(f"✅ 版面分析完成，共分析 {result.total_pages} 页")
            return True
            
        except Exception as e:
            step_duration = time.time() - step_start_time
            self._print_timing_info("版面分析（失败）", step_duration)
            print(f"❌ 版面分析失败: {e}")
            return False
    
    def step2_ocr_recognition_and_format(self):
        """步骤2: OCR识别与格式转换 - 使用ONNX OCR脚本直接处理PDF文件"""
        print("=" * 60)
        print("步骤2: 开始OCR识别与格式转换...")
        step_start_time = time.time()
        
        try:
            # 使用新的ONNX OCR脚本
            ocr_script = Path(__file__).parent / "ppocr" / "onnx_ocr.py"
            onnxocr_dir = Path(__file__).parent / "ppocr"
            
            if not ocr_script.exists():
                print(f"❌ ONNX OCR脚本不存在: {ocr_script}")
                return False
            
            # 直接使用PDF文件作为输入
            pdf_path = self.input_pdf_path
            if not pdf_path.exists():
                print(f"❌ PDF文件不存在: {pdf_path}")
                return False
            
            print(f"📄 开始OCR文字识别...")
            
            # 构建新的OCR命令 - 使用ONNX OCR脚本
            cmd = [
                "python", "onnx_ocr.py",
                "--input", str(pdf_path.absolute()),
                "--output_name", self.pdf_name,
                "--output_dir", "results"
            ]
            
            # 在ppocr目录下执行命令
            print(f"🔄 正在执行ONNX OCR识别...")
            
            result = subprocess.run(
                cmd,
                cwd=str(onnxocr_dir),
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"❌ OCR执行失败，返回码: {result.returncode}")
                if result.stderr:
                    print(f"错误信息: {result.stderr}")
                if result.stdout:
                    print(f"输出信息: {result.stdout}")
                return False
            
            # 查找生成的OCR结果文件
            print(f"🔍 查找OCR结果文件...")
            
            # 根据新的命名格式构建期望的文件名
            expected_filename = f"{self.pdf_name}_ppocr_results.json"
            expected_file_path = onnxocr_dir / "results" / expected_filename
            
            ocr_result_file = None
            
            # 首先尝试精确匹配
            if expected_file_path.exists():
                ocr_result_file = expected_file_path
                print(f"✅ 找到OCR结果文件: {expected_file_path}")
            else:
                # 列出results目录中的所有文件以便调试
                results_dir = onnxocr_dir / "results"
                if results_dir.exists():
                    result_files = list(results_dir.glob("*.json"))
                    print(f"📂 results目录中的文件: {[f.name for f in result_files]}")
                    
                    # 尝试查找包含PDF名称的文件
                    for result_file in result_files:
                        if self.pdf_name in result_file.name and "ppocr_results" in result_file.name:
                            ocr_result_file = result_file
                            print(f"✅ 找到匹配的OCR结果文件: {result_file}")
                            break
                
                # 如果仍然没找到，回退到通用搜索
                if not ocr_result_file:
                    print("🔄 尝试通用搜索...")
                    possible_patterns = ["*results*.json", "*result*.json", "*.json"]
                    
                    for pattern in possible_patterns:
                        matching_files = list(results_dir.glob(pattern))
                        if matching_files:
                            # 选择最新的文件
                            ocr_result_file = max(matching_files, key=lambda f: f.stat().st_mtime)
                            print(f"✅ 找到最新的结果文件: {ocr_result_file}")
                            break
            
            if not ocr_result_file:
                step_duration = time.time() - step_start_time
                self._print_timing_info("OCR识别（失败）", step_duration)
                print("❌ 未找到OCR结果文件")
                return False
            
            # 复制结果文件到期望的位置
            shutil.copy2(ocr_result_file, self.ppocr_output_file)
            print(f"✅ OCR识别完成")
            
            # 立即进行格式转换
            print("🔄 开始转换OCR格式...")
            
            if convert_to_flat_format is None:
                print("❌ convert_to_flat_format模块未正确导入")
                return False
            
            # 使用convert_points_to_bbox转换格式
            flat_results = convert_to_flat_format(
                str(self.ppocr_output_file),
                str(self.ppocr_bbox_file)
            )
            
            step_duration = time.time() - step_start_time
            self._print_timing_info("OCR识别与格式转换", step_duration)
            
            print(f"✅ OCR识别与格式转换全部完成")
            return True
                
        except Exception as e:
            step_duration = time.time() - step_start_time
            self._print_timing_info("OCR识别与格式转换（异常）", step_duration)
            print(f"❌ OCR识别与格式转换失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def step3_merge_blocks_ocr(self):
        """步骤3: 合并版面块和OCR结果"""
        print("=" * 60)
        print("步骤3: 合并版面块和OCR结果...")
        
        if merge_blocks_and_ocr is None:
            print("❌ merge_blocks_and_ocr模块未正确导入")
            return False
        
        try:
            # 合并blocks和OCR结果
            merge_blocks_and_ocr(
                str(self.blocks_info_file),
                str(self.ppocr_bbox_file),
                str(self.merged_file)
            )
            
            print(f"✅ 合并完成")
            return True
            
        except Exception as e:
            print(f"❌ 合并失败: {e}")
            return False
    
    def step4_sort_reading_order(self):
        """步骤4: 文本框阅读顺序排序"""
        print("=" * 60)
        print("步骤4: 文本框阅读顺序排序...")
        step_start_time = time.time()
        
        if process_textboxes_reading_order is None:
            print("❌ process_textboxes_reading_order模块未正确导入")
            return False
        
        try:
            # 使用LayoutReader模型排序
            process_textboxes_reading_order(
                str(self.merged_file),
                str(self.sorted_file)
            )
            
            step_duration = time.time() - step_start_time
            self._print_timing_info("阅读顺序识别", step_duration)
            
            print(f"✅ 阅读顺序排序完成")
            return True
            
        except Exception as e:
            step_duration = time.time() - step_start_time
            self._print_timing_info("阅读顺序识别（失败）", step_duration)
            print(f"❌ 阅读顺序排序失败: {e}")
            return False
    
    def step5_generate_markdown(self):
        """步骤5: 生成Markdown文档"""
        print("=" * 60)
        print("步骤5: 生成Markdown文档...")
        
        if convert_json_to_markdown is None:
            print("❌ convert_json_to_markdown模块未正确导入")
            return False
        
        try:
            # 首先复制版面分析产生的切分图片到images目录
            self._copy_layout_images()
            
            # 生成Markdown
            convert_json_to_markdown(
                str(self.sorted_file),
                str(self.final_markdown)
            )
            
            # 更新Markdown中的图片路径
            self._update_markdown_image_paths()
            
            print(f"✅ Markdown生成完成")
            return True
            
        except Exception as e:
            print(f"❌ Markdown生成失败: {e}")
            return False
    
    def _copy_layout_images(self):
        """复制版面分析产生的切分图片（crops）到images目录"""
        print("🖼️  开始复制版面分析切分图片...")
        
        try:
            # 先清空images目录
            if self.images_dir.exists():
                shutil.rmtree(self.images_dir)
            
            # 重新创建images目录
            self.images_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制crops中的切分图片（用于Markdown显示）
            crops_dir = self.layout_output_dir / "crops"
            
            if crops_dir.exists():
                copied_count = 0
                skipped_count = 0
                
                for img_file in crops_dir.iterdir():
                    if img_file.is_file() and img_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']:
                        try:
                            shutil.copy2(img_file, self.images_dir)
                            copied_count += 1
                        except Exception as e:
                            skipped_count += 1
                    else:
                        skipped_count += 1
                
                print(f"📊 成功复制 {copied_count} 个图片文件")
                
                if copied_count == 0:
                    print("⚠️  警告: 没有找到可复制的图片文件")
                    
            else:
                print(f"⚠️  警告: 未找到切分图片目录")
                
                # 检查是否有其他可能的图片目录
                layout_output_files = list(self.layout_output_dir.glob("**/*"))
                image_files = [f for f in layout_output_files 
                              if f.is_file() and f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']]
                
                if image_files:
                    print(f"🔄 尝试从其他位置复制 {len(image_files)} 个图片...")
                    copied_count = 0
                    for img_file in image_files:
                        try:
                            shutil.copy2(img_file, self.images_dir)
                            copied_count += 1
                        except Exception as e:
                            pass
                    
                    print(f"📊 从备用位置复制了 {copied_count} 个图片")
                else:
                    print("❌ 未找到任何图片文件")
            
        except Exception as e:
            print(f"❌ 复制图片过程中出现错误: {e}")
    
    def _update_markdown_image_paths(self):
        """更新Markdown文件中的图片路径"""
        try:
            if not self.final_markdown.exists():
                return
            
            # 读取Markdown内容
            with open(self.final_markdown, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新图片路径
            # 将形如 ![图片描述](原路径/图片.png) 替换为 ![图片描述](images/图片.png)
            def replace_image_path(match):
                alt_text = match.group(1)
                original_path = match.group(2)
                image_name = Path(original_path).name
                return f'![{alt_text}](images/{image_name})'
            
            # 使用正则表达式替换图片路径
            updated_content = re.sub(
                r'!\[(.*?)\]\((.*?)\)',
                replace_image_path,
                content
            )
            
            # 写回文件
            with open(self.final_markdown, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            print("✅ Markdown图片路径已更新")
            
        except Exception as e:
            print(f"❌ 更新Markdown图片路径失败: {e}")
    
    def cleanup_temp_files(self):
        """清理临时文件，但保留images目录"""
        try:
            if self.temp_dir.exists():
                # 清理temp目录，但保留重要的输出文件
                print("🧹 开始清理临时文件...")
                
                # 列出要删除的文件类型
                temp_files_deleted = 0
                for item in self.temp_dir.iterdir():
                    if item.is_file():
                        try:
                            item.unlink()
                            temp_files_deleted += 1
                        except Exception as e:
                            pass
                    elif item.is_dir():
                        try:
                            shutil.rmtree(item)
                        except Exception as e:
                            pass
                
                # 删除空的temp目录
                if self.temp_dir.exists() and not list(self.temp_dir.iterdir()):
                    self.temp_dir.rmdir()
                
                print(f"✅ 临时文件清理完成")
                
        except Exception as e:
            print(f"❌ 清理临时文件失败: {e}")
    
    def run_pipeline(self, cleanup=True, parallel_execution=True):
        """运行完整流水线
        
        Args:
            cleanup: 是否清理临时文件
            parallel_execution: 是否并行执行步骤1和步骤2
        """
        print(f"📄 开始处理文件: {self.input_pdf_path.name}")
        print(f"🚀 执行模式: {'并行执行' if parallel_execution else '顺序执行'}")
        
        # 记录总流程开始时间
        self.pipeline_start_time = time.time()
        
        if parallel_execution:
            # 并行执行步骤1和步骤2
            success_count = self._run_parallel_steps()
            if success_count < 2:
                return False
        else:
            # 顺序执行所有步骤
            steps = [
                ("版面分析", self.step1_layout_analysis),
                ("OCR识别与格式转换", self.step2_ocr_recognition_and_format),
            ]
            
            success_count = 0
            for step_name, step_func in steps:
                if step_func():
                    success_count += 1
                else:
                    print(f"步骤 '{step_name}' 失败，流水线终止")
                    return False
        
        # 继续执行后续步骤（这些步骤需要顺序执行）
        sequential_steps = [
            ("合并版面块和OCR", self.step3_merge_blocks_ocr),
            ("文本框阅读顺序排序", self.step4_sort_reading_order),
            ("生成Markdown文档", self.step5_generate_markdown),
        ]
        
        for step_name, step_func in sequential_steps:
            if step_func():
                success_count += 1
            else:
                print(f"步骤 '{step_name}' 失败，流水线终止")
                break
        
        # 计算总流程时间
        total_duration = time.time() - self.pipeline_start_time
        
        # 打印详细的时间报告
        total_steps = 5  # 总共5个步骤
        self._print_timing_report(total_duration, success_count, total_steps)
        
        # 清理临时文件
        if cleanup and success_count == total_steps:
            self.cleanup_temp_files()
        
        # 输出结果
        if success_count == total_steps:
            print("=" * 60)
            print("🎉 执行成功！")
            # print(f"📁 输出目录: {self.output_dir}")
        else:
            print("=" * 60)
            print(f"❌ 执行失败，完成 {success_count}/{total_steps} 个步骤")
        
        return success_count == total_steps
    
    def _run_parallel_steps(self):
        """并行执行步骤1和步骤2"""
        print("=" * 60)
        print("🔄 并行执行步骤1和步骤2...")
        parallel_start_time = time.time()
        
        # 使用线程池并行执行步骤1和步骤2
        with ThreadPoolExecutor(max_workers=2) as executor:
            # 提交任务
            future_layout = executor.submit(self.step1_layout_analysis)
            future_ocr = executor.submit(self.step2_ocr_recognition_and_format)
            
            # 等待并获取结果
            layout_success = future_layout.result()
            ocr_success = future_ocr.result()
        
        parallel_duration = time.time() - parallel_start_time
        print(f"⏱️  并行执行耗时: {self._format_duration(parallel_duration)}")
        
        # 检查并行步骤是否都成功
        success_count = 0
        if layout_success:
            success_count += 1
            print("✅ 步骤1 '版面分析' 成功")
        else:
            print("❌ 步骤1 '版面分析' 失败")
        
        if ocr_success:
            success_count += 1
            print("✅ 步骤2 'OCR识别与格式转换' 成功")
        else:
            print("❌ 步骤2 'OCR识别与格式转换' 失败")
        
        if success_count == 2:
            print("✅ 并行步骤执行成功")
        
        return success_count
    
    def _print_timing_report(self, total_duration, success_count, total_steps):
        """打印详细的时间报告"""
        print("=" * 60)
        print("⏱️  详细时间报告")
        print("=" * 60)
        
        # 打印各步骤耗时
        key_steps = ["版面分析", "OCR识别与格式转换", "阅读顺序识别"]
        
        for step_name in key_steps:
            if step_name in self.timing_results:
                formatted_time = self._format_duration(self.timing_results[step_name])
                print(f"📊 {step_name:<16}: {formatted_time}")
        
        # 计算并行执行的时间优势
        layout_time = self.timing_results.get("版面分析", 0)
        ocr_time = self.timing_results.get("OCR识别与格式转换", 0)
        
        if layout_time > 0 and ocr_time > 0:
            sequential_time = layout_time + ocr_time
            parallel_time = max(layout_time, ocr_time)
            time_saved = sequential_time - parallel_time
            
            print(f"📊 {'并行执行收益':<16}: 节省 {self._format_duration(time_saved)}")
            print(f"📊 {'顺序执行需要':<16}: {self._format_duration(sequential_time)}")
            print(f"📊 {'并行执行实际':<16}: {self._format_duration(parallel_time)}")
        
        # 计算其他步骤总时间
        key_steps_time = sum(self.timing_results.get(step, 0) for step in key_steps)
        other_steps_time = total_duration - key_steps_time
        
        if other_steps_time > 0:
            formatted_other_time = self._format_duration(other_steps_time)
            print(f"📊 {'其他步骤':<16}: {formatted_other_time}")
        
        print("-" * 60)
        formatted_total_time = self._format_duration(total_duration)
        print(f"🕐 总流程耗时: {formatted_total_time}")
        
        if success_count == total_steps:
            print(f"✅ 所有步骤都成功完成")
        else:
            print(f"⚠️  完成 {success_count}/{total_steps} 个步骤")
        
        print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="PDF文档处理完整流水线")
    parser.add_argument("-i", "--input_pdf", help="输入PDF文件路径")
    parser.add_argument("-o", "--output", default="results", help="输出基础目录（默认：results）")
    parser.add_argument("--keep-temp", action="store_true", help="保留临时文件")
    parser.add_argument("--sequential", action="store_true", help="使用顺序执行模式（默认为并行执行）")
    
    args = parser.parse_args()
    
    # 检查输入文件
    if not Path(args.input_pdf).exists():
        print(f"错误：输入文件不存在 - {args.input_pdf}")
        return 1
    
    # 创建流水线并执行
    pipeline = DocumentProcessingPipeline(args.input_pdf, args.output)
    success = pipeline.run_pipeline(
        cleanup=not args.keep_temp,
        parallel_execution=not args.sequential
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
