#!/usr/bin/env python
# 增强型 Markdown 解密工具，提供批量解密和额外功能
import os
import sys
import glob
import argparse

# 确保可以导入加密模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'remote'))

try:
    from remote.crypto_utils import decrypt_text
except ImportError:
    try:
        from crypto_utils import decrypt_text
    except ImportError:
        print("错误: 无法导入加密模块。请确保 crypto_utils.py 在当前目录或 'remote' 子目录中。")
        sys.exit(1)

def decrypt_file(input_file, output_file=None, key=None, quiet=False, force=False):
    """解密单个 Markdown 文件"""
    # 设置密钥
    if not key:
        key = os.environ.get('MARKDOWN_ENCRYPT_KEY', 'default-strong-key-1234567890')
    
    # 设置输出文件名
    if not output_file:
        base_name = os.path.basename(input_file)
        dir_name = os.path.dirname(input_file)
        file_name_without_ext, ext = os.path.splitext(base_name)
        output_file = os.path.join(dir_name, f"{file_name_without_ext}.decrypted{ext}")
    
    # 检查输出文件是否已存在
    if os.path.exists(output_file) and not force:
        if not quiet:
            print(f"警告: 输出文件已存在 - {output_file}")
            choice = input("是否覆盖? (y/n): ").lower()
            if choice != 'y':
                print("已取消")
                return False
    
    try:
        # 读取加密内容
        with open(input_file, 'r', encoding='utf-8') as f:
            encrypted_content = f.read()
        
        # 尝试解密
        try:
            decrypted_content = decrypt_text(encrypted_content, key)
            
            # 写入解密后的内容
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(decrypted_content)
            
            if not quiet:
                print(f"解密成功！解密后的文件已保存到: {output_file}")
            return True
        except Exception as e:
            if not quiet:
                print(f"解密失败，可能是明文文件或密钥不正确: {e}")
            
            # 如果强制模式，则复制原始内容
            if force:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(encrypted_content)
                if not quiet:
                    print(f"已将原始内容复制到: {output_file}")
            return False
    except Exception as e:
        if not quiet:
            print(f"读取文件时出错: {e}")
        return False

def batch_decrypt(input_pattern, key=None, force=False):
    """批量解密匹配模式的所有文件"""
    files = glob.glob(input_pattern)
    if not files:
        print(f"没有找到匹配的文件: {input_pattern}")
        return
    
    print(f"找到 {len(files)} 个文件匹配模式: {input_pattern}")
    success_count = 0
    
    for file in files:
        print(f"处理文件: {file}")
        if decrypt_file(file, key=key, quiet=True, force=force):
            success_count += 1
    
    print(f"批量处理完成: {success_count}/{len(files)} 个文件解密成功")

def main():
    parser = argparse.ArgumentParser(description='解密由 LLM 生成的加密 Markdown 文件')
    parser.add_argument('input', help='输入的加密文件路径或通配符模式(例如 "*.md")')
    parser.add_argument('-o', '--output', help='输出的解密文件路径(单文件模式时有效)')
    parser.add_argument('-k', '--key', help='解密密钥(默认使用环境变量MARKDOWN_ENCRYPT_KEY)')
    parser.add_argument('-f', '--force', action='store_true', help='强制模式，覆盖现有文件并忽略错误')
    parser.add_argument('-b', '--batch', action='store_true', help='批量模式，处理所有匹配的文件')
    
    args = parser.parse_args()
    
    # 设置密钥
    key = args.key or os.environ.get('MARKDOWN_ENCRYPT_KEY', 'default-strong-key-1234567890')
    
    # 批量模式
    if args.batch or '*' in args.input or '?' in args.input:
        batch_decrypt(args.input, key, args.force)
    else:
        # 单文件模式
        decrypt_file(args.input, args.output, key, force=args.force)

if __name__ == '__main__':
    main()
