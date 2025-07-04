# 测试 ollama-python 的功能
import os
# 临时禁用代理设置，避免 ollama 连接问题
proxy_env_vars = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 
                  'ALL_PROXY', 'all_proxy', 'ftp_proxy', 'FTP_PROXY']
original_proxy_values = {}
for var in proxy_env_vars:
    if var in os.environ:
        original_proxy_values[var] = os.environ[var]
        del os.environ[var]

import ollama

# 恢复代理设置
for var, value in original_proxy_values.items():
    os.environ[var] = value
import time
import os
import argparse
import sys
import json  # 增加json模块导入，用于解析加密协议信息
import base64  # 添加base64模块，用于处理base64编码的内容
import re  # 添加正则表达式模块

# 定义默认模型名称作为全局常量
DEFAULT_MODEL_NAME = "qwen2.5:1.5b"
# DEFAULT_MODEL_NAME = "qwen3:1.7b"

# 添加以下函数来读取markdown文件
sys.path.append(os.path.join(os.path.dirname(__file__), 'remote'))
# 尝试导入加密解密模块
try:
    from remote.crypto_utils import decrypt_text
    from remote.crypto_utils import decrypt_text_protocol1, decrypt_text_protocol2, decrypt_text_protocol3
    HAS_CRYPTO = True
except ImportError:
    try:
        from crypto_utils import decrypt_text
        from crypto_utils import decrypt_text_protocol1, decrypt_text_protocol2, decrypt_text_protocol3
        HAS_CRYPTO = True
    except ImportError:
        # 兼容未找到模块的情况
        decrypt_text = None
        decrypt_text_protocol1 = None
        decrypt_text_protocol2 = None
        decrypt_text_protocol3 = None
        HAS_CRYPTO = False

def read_markdown(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        # 检测是否为加密内容（base64+AES，长度较长且无markdown格式特征）
        if decrypt_text is not None and len(content) > 100 and not content.lstrip().startswith('#'):
            # 尝试用密钥解密（密钥可通过环境变量传递）
            key = os.environ.get('MARKDOWN_ENCRYPT_KEY', 'default-strong-key-1234567890')
            
            # 尝试多种解密方法
            plain = None
            error_msg = ""
            
            # 1. 首先尝试标准解密函数（会自动检测协议）
            try:
                plain = decrypt_text(content, key)
                print("[DEBUG] 标准解密成功，明文前200字：\n", plain[:200] if plain else "")
            except Exception as e:
                error_msg = str(e)
                print(f"[DEBUG] 标准解密失败: {e}")
                
                # 2. 依次尝试所有解密协议
                print("[DEBUG] 依次尝试所有解密协议...")
                
                # 先检查是否为base64编码的JSON（协议2和协议3通常这样存储）
                try:
                    # 注意：某些系统可能将文件内容添加了空行或空格，需要清理
                    cleaned_content = content.strip()
                    decoded_content = base64.b64decode(cleaned_content).decode('utf-8')
                    if decoded_content.startswith('{') and decoded_content.endswith('}'):
                        data = json.loads(decoded_content)
                        protocol = data.get("metadata", {}).get("protocol")
                        print(f"[DEBUG] 检测到加密协议: {protocol}")
                except Exception as b64_e:
                    protocol = None
                    print(f"[DEBUG] base64解析失败: {b64_e}")
                
                # 尝试协议2解密
                if not plain:
                    try:
                        print("[DEBUG] 尝试使用协议2解密...")
                        plain = decrypt_text_protocol2(content, key)
                        print("[DEBUG] 协议2解密成功")
                    except Exception as p2_e:
                        print(f"[DEBUG] 协议2解密失败: {p2_e}")
                
                # 尝试协议3解密
                if not plain:
                    try:
                        print("[DEBUG] 尝试使用协议3解密...")
                        plain = decrypt_text_protocol3(content, key)
                        print("[DEBUG] 协议3解密成功")
                    except Exception as p3_e:
                        print(f"[DEBUG] 协议3解密失败: {p3_e}")
                
                # 尝试协议1解密 
                if not plain:
                    try:
                        print("[DEBUG] 尝试使用协议1解密...")
                        plain = decrypt_text_protocol1(content, key)
                        print("[DEBUG] 协议1解密成功")
                    except Exception as p1_e:
                        print(f"[DEBUG] 协议1解密失败: {p1_e}")
                        
                # 如果上面都失败，直接尝试解析原始内容为JSON（某些情况下可能是明文JSON）
                if not plain and content.lstrip().startswith('{'):
                    try:
                        data = json.loads(content)
                        protocol = data.get("metadata", {}).get("protocol")
                        if protocol:
                            print(f"[DEBUG] 检测到明文JSON中的协议: {protocol}")
                            if protocol == 1:
                                plain = decrypt_text_protocol1(data.get("data", ""), key)
                            elif protocol == 2:
                                plain = decrypt_text_protocol2(data.get("data", ""), key)
                            elif protocol == 3:
                                plain = decrypt_text_protocol3(data.get("data", ""), key)
                    except Exception as json_e:
                        print(f"[DEBUG] JSON解析失败: {json_e}")
            
            # 如果任何方法解密成功，返回解密内容
            if plain:
                # 过滤图片引用，避免大模型API阻塞
                plain = filter_images(plain)
                return plain
            else:
                print(f"[DEBUG] 自动解密Markdown失败，按原文返回: {error_msg}")
                content = filter_images(content)
                return content
        
        print("[DEBUG] 读取明文Markdown，前200字：\n", content[:200])
        # 过滤图片引用，避免大模型API阻塞
        content = filter_images(content)
        return content
    except Exception as e:
        print(f"读取markdown文件出错: {e}")
        return ""

# 过滤图片引用函数，避免大模型API因图片引用而阻塞
def filter_images(md_content):
    """去除所有图片引用，避免大模型API阻塞"""
    if not md_content:
        return md_content
    # 去除所有图片引用 ![描述](链接)
    filtered = re.sub(r'!\[.*?\]\(.*?\)', '', md_content)
    print(f"[DEBUG] 过滤图片引用: 原始长度 {len(md_content)} -> 过滤后长度 {len(filtered)}")
    return filtered

# 修改read_document函数，添加更详细的调试输出
def read_document(file_path):
    """根据文件扩展名选择相应的读取方法"""
    print(f"尝试读取文件: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return ""
        
    if file_path.lower().endswith('.md') or file_path.lower().endswith('.markdown'):
        content = read_markdown(file_path)
        if not content:
            print(f"读取markdown文件失败或文件为空: {file_path}")
        else:
            print(f"成功读取markdown文件，内容长度: {len(content)} 字符")
        return content
    else:
        print(f"不支持的文件格式: {file_path}")
        return ""

# 分点提炼提示模板
POINT_EXTRACTION_TEMPLATE = """
你是一个专业的内容分析助手。请对以下文档内容进行分析和提炼，按照以下结构输出：

## 核心主题
简明扼要地概括整个文档的核心主题（100字以内）

## 关键要点
提取文档中的5-7个最重要要点，用简洁的短句表达，每个要点不超过30字，使用无序列表格式。

## 内容提炼
以层级结构方式提炼文档的详细内容：
1. 第一层级为主要部分/章节（用二级标题）
   1.1 第二层级为该部分的关键内容（用三级标题）
      - 第三层级为具体要点（用无序列表）

## 重要引述
提取文档中2-3个最具代表性的原文引述，使用引用格式标注

## 结论与启示
总结文档的结论或给出的启示（150字以内）

## 行动建议
提供2-3条基于文档内容的实用行动建议

请确保输出格式规范，采用Markdown语法，结构清晰，便于阅读。
"""

# 翻译模式提示模板
TRANSLATION_TEMPLATE = """
你是一位专业的翻译专家。请将以下文档内容翻译成中文（或根据需要翻译成英文），同时遵循以下翻译原则：

## 翻译要求
1. 保持原文的意思、语气和风格
2. 确保专业术语翻译准确，必要时保留原文术语并在括号中注明翻译
3. 使翻译后的文本流畅自然，符合目标语言的表达习惯
4. 保留原文的段落结构和格式

## 专业术语处理
- 对于专业术语，首次出现时可使用"术语(翻译)"或"翻译(术语)"的形式
- 同一术语在全文中保持一致的翻译

## 文档结构
- 保留原文的标题、小标题和层级结构
- 保留原文的列表、表格等格式元素
- 保留原文的引用和脚注，并进行相应翻译

## 输出格式
1. 翻译后的文本应使用Markdown格式
2. 对于无法确定准确翻译的内容，请在翻译后的文本中用[待确认]标注

请首先理解整篇文档的主题和内容，然后进行翻译，确保翻译后的文本专业、准确、连贯。
"""

# 修改write_to_markdown函数以支持翻译模式和加密输出
def write_to_markdown(content, source_file_path, model_name, mode="summary"):
    try:
        # 从源文件路径获取基本名称
        base_name = os.path.basename(source_file_path)
        file_name_without_ext = os.path.splitext(base_name)[0]
        
        # 获取源文件所在目录（不再创建额外的output子目录）
        output_dir = os.path.dirname(source_file_path)
        
        # 根据模式设置文件名后缀
        if mode == "summary":
            suffix = "_总结"
            title_suffix = "内容总结"
        elif mode == "extraction":
            suffix = "_分点提炼"
            title_suffix = "分点提炼"
        elif "translation" in mode:
            suffix = mode.replace("translation", "")  # 获取翻译方向后缀
            title_suffix = "文档翻译" + suffix
        
        # 创建markdown文件路径
        output_path = os.path.join(output_dir, f"{file_name_without_ext}{suffix}.md")
        
        # 准备完整内容（带有元信息）
        full_content = f"# {file_name_without_ext} {title_suffix}\n\n"
        full_content += f"**源文件**: {base_name}\n"
        full_content += f"**生成模型**: {model_name}\n"
        full_content += f"**生成时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        full_content += "---\n\n"
        full_content += content
        
        # 加密处理
        try:
            # 尝试导入加密模块
            if 'decrypt_text' in globals():
                # 如果已经导入了解密函数，那么对应的加密函数应该也存在同一模块中
                encrypt_text_fn = sys.modules.get(decrypt_text.__module__).encrypt_text
                key = os.environ.get('MARKDOWN_ENCRYPT_KEY', 'default-strong-key-1234567890')
                
                # 加密输出内容，加密函数会随机选择一种加密协议
                encrypted_content = encrypt_text_fn(full_content, key)
                print(f"[INFO] 内容已加密: {len(full_content)} -> {len(encrypted_content)} 字符")
                
                # 尝试解析加密内容，确认其包含协议信息
                try:
                    data = json.loads(encrypted_content)
                    protocol = data.get("metadata", {}).get("protocol", 1)
                    print(f"[INFO] 使用加密协议: {protocol}")
                except:
                    print("[WARN] 无法检测加密协议信息")
            else:
                print("[WARN] 未找到加密模块，输出明文内容")
                encrypted_content = full_content
        except Exception as e:
            print(f"[WARN] 加密失败，输出明文内容: {e}")
            encrypted_content = full_content
        
        # 写入内容到markdown文件
        with open(output_path, 'w', encoding='utf-8') as md_file:
            md_file.write(encrypted_content)
            
        print(f"内容已保存到: {output_path}")
        return output_path
    except Exception as e:
        print(f"写入markdown文件出错: {e}")
        return None

# 添加处理特定模式的函数
def process_summary(input_file_path):
    """处理摘要模式"""
    prompt = read_document(input_file_path)  # 使用新的通用读取函数
    
    if not prompt:
        return {"error": "文档内容为空或读取失败"}
    
    messages = [
        {"role": "system", "content": "你是一个办公助手，帮我总结这个文档的要点"},
        {"role": "user", "content": prompt}
    ]
    
    try:
        print(f"开始调用大模型API，模型: {DEFAULT_MODEL_NAME}, 内容长度: {len(prompt)} 字符")
        start_time = time.time()
        response = ollama.chat(model=DEFAULT_MODEL_NAME, messages=messages)
        end_time = time.time()
        
        model_reply = response['message']['content']
        elapsed_time = end_time - start_time
        
        print(f"大模型API调用成功，耗时 {elapsed_time:.2f} 秒，回复长度: {len(model_reply)} 字符")
        markdown_file = write_to_markdown(model_reply, input_file_path, DEFAULT_MODEL_NAME, "summary")
        
        return {
            "output_file": markdown_file,
            "processing_time": elapsed_time
        }
    except Exception as e:
        print(f"调用大模型API出错: {e}")
        raise

def process_extraction(input_file_path):
    """处理分点提炼模式"""
    prompt = read_document(input_file_path)  # 使用新的通用读取函数
    
    if not prompt:
        return {"error": "文档内容为空或读取失败"}
    
    messages = [
        {"role": "system", "content": POINT_EXTRACTION_TEMPLATE},
        {"role": "user", "content": prompt}
    ]
    
    try:
        print(f"开始调用大模型API，模型: {DEFAULT_MODEL_NAME}, 内容长度: {len(prompt)} 字符")
        start_time = time.time()
        response = ollama.chat(model=DEFAULT_MODEL_NAME, messages=messages)
        end_time = time.time()
        
        model_reply = response['message']['content']
        elapsed_time = end_time - start_time
        
        print(f"大模型API调用成功，耗时 {elapsed_time:.2f} 秒，回复长度: {len(model_reply)} 字符")
        markdown_file = write_to_markdown(model_reply, input_file_path, DEFAULT_MODEL_NAME, "extraction")
        
        return {
            "output_file": markdown_file,
            "processing_time": elapsed_time
        }
    except Exception as e:
        print(f"调用大模型API出错: {e}")
        raise

def process_translation(input_file_path, trans_direction="1"):
    """处理翻译模式"""
    prompt = read_document(input_file_path)  # 使用新的通用读取函数
    
    if not prompt:
        return {"error": "文档内容为空或读取失败"}
    
    if trans_direction == "1":
        translation_instruction = TRANSLATION_TEMPLATE.replace("翻译成中文（或根据需要翻译成英文）", "翻译成英文")
        suffix = "_中译英"
    else:
        translation_instruction = TRANSLATION_TEMPLATE.replace("翻译成中文（或根据需要翻译成英文）", "翻译成中文")
        suffix = "_英译中"
        
    messages = [
        {"role": "system", "content": translation_instruction},
        {"role": "user", "content": prompt}
    ]
    
    try:
        print(f"开始调用大模型API，模型: {DEFAULT_MODEL_NAME}, 内容长度: {len(prompt)} 字符")
        start_time = time.time()
        response = ollama.chat(model=DEFAULT_MODEL_NAME, messages=messages)
        end_time = time.time()
        
        model_reply = response['message']['content']
        elapsed_time = end_time - start_time
        
        print(f"大模型API调用成功，耗时 {elapsed_time:.2f} 秒，回复长度: {len(model_reply)} 字符")
        markdown_file = write_to_markdown(model_reply, input_file_path, DEFAULT_MODEL_NAME, "translation" + suffix)
        
        return {
            "output_file": markdown_file,
            "processing_time": elapsed_time
        }
    except Exception as e:
        print(f"调用大模型API出错: {e}")
        raise

# 添加参数解析
def parse_args():
    parser = argparse.ArgumentParser(description='处理文档内容')
    parser.add_argument('--input', '-i', required=True, help='输入文件路径')
    parser.add_argument('--mode', '-m', choices=['summary', 'extraction', 'translation'], 
                        default='summary', help='处理模式')
    parser.add_argument('--translation_direction', '-t', choices=['1', '2'], 
                        help='翻译方向 (1:中译英, 2:英译中)')
    return parser.parse_args()

# 修改main函数，支持从命令行调用
def main():
    try:
        # 初始化变量，防止未定义错误
        choice = None
        mode_choice = None
        trans_direction = None
        
        # 解析命令行参数
        if len(sys.argv) > 1:  # 如果有命令行参数
            args = parse_args()
            input_file_path = args.input
            mode_choice = args.mode
            trans_direction = args.translation_direction
        else:
            # 原有的交互式逻辑
            # 读取文档内容
            input_file_path = "/home/m/Documents/integrate_layout_web/MinerU/remote/output/demo-1/demo-1.md"
            if not os.path.exists(input_file_path):
                print("文件不存在，请检查路径")
                sys.exit(1)
                
            prompt = read_document(input_file_path)
            if not prompt:
                print("文档内容为空或读取失败")
                sys.exit(1)
            
            # 选择处理模式
            print("\n请选择处理模式:")
            print("1. 内容总结 (简单摘要)")
            print("2. 分点提炼 (结构化提取)")
            print("3. 文档翻译 (中英互译)")
            choice = input("请输入选项(1, 2或3): ")
            
            if choice == "1":
                mode_choice = "summary"
                # 其余代码...
            elif choice == "2":
                mode_choice = "extraction"
                # 其余代码...
            else:
                mode_choice = "translation"
                # 询问翻译方向
                trans_direction = input("请选择翻译方向 (1: 中译英, 2: 英译中): ")
                # 其余代码...
        
        # 根据模式选择处理方式
        if not os.path.exists(input_file_path):
            print("文件不存在，请检查路径")
            sys.exit(1)
            
        prompt = read_document(input_file_path)  # 使用通用读取函数
        if not prompt:
            print("文档内容为空或读取失败")
            sys.exit(1)
        
        # 修改判断逻辑，避免使用可能未定义的变量
        if mode_choice == "summary":
            result = process_summary(input_file_path)
        elif mode_choice == "extraction":
            result = process_extraction(input_file_path)
        elif mode_choice == "translation":
            result = process_translation(input_file_path, trans_direction)
        else:
            print("未知的处理模式")
            sys.exit(1)
        
        if "error" in result:
            print(result["error"])
            sys.exit(1)
        else:
            print(f"文档处理完成！用时： {result['processing_time']:.2f} 秒")
            print(f"输出文件: {result['output_file']}")
            sys.exit(0)  # 显式返回成功状态码
    except Exception as e:
        print(f"处理过程中发生错误: {e}")
        sys.exit(1)  # 异常退出时返回错误状态码
        
if __name__ == "__main__":
    main()
