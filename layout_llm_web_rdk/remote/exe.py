# Copyright (c) Opendatalab. All rights reserved.
import os
import sys
import shutil
from pathlib import Path

# 添加当前目录和pipeline.py所在的目录到系统路径
__dir__ = os.path.dirname(os.path.abspath(__file__))
sys.path.append(__dir__)
pipeline_dir = os.path.join(__dir__, '..', 'layout_process')
sys.path.append(pipeline_dir)

try:
    from pipeline import DocumentProcessingPipeline
    from crypto_utils import encrypt_text
except ImportError as e:
    print(f"导入模块失败: {e}")
    sys.exit(1)

ENCRYPT_KEY = os.environ.get('MARKDOWN_ENCRYPT_KEY', 'default-strong-key-1234567890')

# args
__dir__ = os.path.dirname(os.path.abspath(__file__))
# 支持从环境变量获取PDF文件路径
pdf_file_name = os.environ.get('PDF_FILE_PATH', os.path.join(__dir__, "input", "demo-2.pdf"))
name_without_extension = os.path.basename(pdf_file_name).split('.')[0]

# 加密参数 - 直接在代码中设置，True为加密，False为不加密
encrypt_markdown = True  # 设置为 False 不加密，True 为加密

# 打印处理的文件路径，便于调试
# print(f"正在处理文件: {pdf_file_name}")
print(f"Markdown加密: {'开启' if encrypt_markdown else '关闭'}")

# 检查输入文件是否存在
if not os.path.exists(pdf_file_name):
    print(f"错误: PDF文件不存在 - {pdf_file_name}")
    sys.exit(1)

# prepare env - 保持与原exe.py相同的输出目录结构
local_image_dir = os.path.join(__dir__, "output", name_without_extension, "images")
local_md_dir = os.path.join(__dir__, "output", name_without_extension)
os.makedirs(local_image_dir, exist_ok=True)
os.makedirs(local_md_dir, exist_ok=True)

try:
    # 创建临时输出目录用于pipeline处理
    temp_output_dir = os.path.join(__dir__, "temp_pipeline_output")
    
    # 创建DocumentProcessingPipeline实例
    pipeline = DocumentProcessingPipeline(pdf_file_name, temp_output_dir)
    
    # 运行pipeline流水线
    # print("开始使用pipeline处理文档...")
    success = pipeline.run_pipeline(cleanup=True)
    
    if not success:
        print("Pipeline处理失败")
        sys.exit(1)
    
    # 读取pipeline生成的markdown文件
    pipeline_md_file = pipeline.final_markdown
    if not pipeline_md_file.exists():
        # print(f"Pipeline未生成markdown文件: {pipeline_md_file}")
        sys.exit(1)
    
    with open(pipeline_md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # 复制pipeline生成的图片到目标目录
    if pipeline.images_dir.exists():
        # 清空目标图片目录
        if os.path.exists(local_image_dir):
            shutil.rmtree(local_image_dir)
        os.makedirs(local_image_dir, exist_ok=True)
        
        # 复制所有图片文件
        for img_file in pipeline.images_dir.iterdir():
            if img_file.is_file() and img_file.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
                shutil.copy2(img_file, local_image_dir)
        # print(f"已复制图片文件到: {local_image_dir}")
    
    # 根据加密参数决定是否加密markdown内容
    if encrypt_markdown:
        print("正在加密Markdown内容...")
        final_md_content = encrypt_text(md_content, ENCRYPT_KEY)
        print("Markdown内容已加密")
    else:
        print("不加密Markdown内容")
        final_md_content = md_content
    
    # 保存最终markdown文件到目标位置
    md_file_path = f"{name_without_extension}.md"
    final_md_path = os.path.join(local_md_dir, md_file_path)
    with open(final_md_path, 'w', encoding='utf-8') as f:
        f.write(final_md_content)
    
    # if encrypt_markdown:
        # print(f"生成加密Markdown文件: {md_file_path}")
    # else:
        # print(f"生成Markdown文件: {md_file_path}")
    
    # print("文本提取和图像生成完成")
    # print(f"文档处理完成: {pdf_file_name}")
    print(f"文档处理完成")
    
    # 清理临时目录
    if os.path.exists(temp_output_dir):
        shutil.rmtree(temp_output_dir)
        print("临时文件已清理")
    
    sys.exit(0)
    
except Exception as e:
    print(f"处理文档时出错: {e}")
    import traceback
    traceback.print_exc()
    
    # 清理临时目录
    temp_output_dir = os.path.join(__dir__, "temp_pipeline_output")
    if os.path.exists(temp_output_dir):
        try:
            shutil.rmtree(temp_output_dir)
        except:
            pass
    
    sys.exit(1)