# decrypt_md.py
# 用于本地解密加密的Markdown文件
# 用法: python decrypt_md.py <加密md路径> [密钥]
import sys
import os
sys.path.append(os.path.dirname(__file__))
from crypto_utils import decrypt_text

if len(sys.argv) < 2:
    print("用法: python decrypt_md.py <加密md路径> [密钥]")
    print("如果不提供密钥，将使用环境变量MARKDOWN_ENCRYPT_KEY或默认密钥")
    sys.exit(1)

enc_md_path = sys.argv[1]

# 获取密钥 - 命令行参数、环境变量或默认值
if len(sys.argv) == 3:
    key = sys.argv[2]  # 命令行参数
else:
    key = os.environ.get('MARKDOWN_ENCRYPT_KEY', '1234567890')  # 环境变量或默认值
    print(f"使用环境变量或默认密钥（首字符: {key[0]}{'*' * (len(key)-2)}{key[-1]}）")

if not os.path.exists(enc_md_path):
    print(f"错误: 文件不存在 - {enc_md_path}")
    sys.exit(1)

with open(enc_md_path, 'r', encoding='utf-8') as f:
    enc_content = f.read()

try:
    # 尝试解密内容
    plain = decrypt_text(enc_content, key)
    print("解密内容如下:\n")
    print(plain[:200] + "..." if len(plain) > 200 else plain)  # 只显示前200字符
    
    # 保存为同目录下 .decrypted.md 文件
    if enc_md_path.endswith('.md'):
        out_path = enc_md_path[:-3] + '.decrypted.md'
    else:
        out_path = enc_md_path + '.decrypted.md'
    
    with open(out_path, 'w', encoding='utf-8') as fout:
        fout.write(plain)
    print(f"\n已保存解密内容到: {out_path}")
except Exception as e:
    print(f"解密失败: {e}")
    print("可能是明文文件或密钥不正确")
    sys.exit(2)
