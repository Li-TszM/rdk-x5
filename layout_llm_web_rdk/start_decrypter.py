#!/usr/bin/env python
# 加密Markdown文件查看器 - 启动脚本
# 自动处理依赖安装、模块导入和GUI启动
import os
import sys
import subprocess
import importlib
import shutil
from pathlib import Path

# 彩色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_colored(text, color):
    print(f"{color}{text}{Colors.ENDC}")

def print_header(text):
    print_colored(f"\n{text}", Colors.HEADER + Colors.BOLD)

def print_success(text):
    print_colored(f"✓ {text}", Colors.GREEN)

def print_warning(text):
    print_colored(f"⚠ {text}", Colors.YELLOW)

def print_error(text):
    print_colored(f"✗ {text}", Colors.RED)

def install_dependencies():
    print_header("检查依赖项...")
    
    # 检查并安装PyCryptodome
    try:
        importlib.import_module('Crypto')
        print_success("已安装PyCryptodome")
    except ImportError:
        print_warning("正在安装PyCryptodome...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pycryptodome"])
            print_success("成功安装PyCryptodome")
        except Exception as e:
            print_error(f"安装PyCryptodome失败: {e}")
            return False
    
    # 检查并安装PyQt5
    try:
        importlib.import_module('PyQt5')
        print_success("已安装PyQt5")
    except ImportError:
        print_warning("正在安装PyQt5...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "PyQt5"])
            print_success("成功安装PyQt5")
        except Exception as e:
            print_error(f"安装PyQt5失败: {e}")
            return False
    
    return True

def fix_imports():
    print_header("检查加密模块导入...")
    
    # 获取路径
    current_dir = Path(__file__).parent.absolute()
    remote_dir = current_dir / "remote"
    
    # 检查crypto_utils.py
    crypto_utils_current = current_dir / "crypto_utils.py"
    crypto_utils_remote = remote_dir / "crypto_utils.py"
    
    if not crypto_utils_remote.exists():
        print_error(f"远程目录中未找到crypto_utils.py: {crypto_utils_remote}")
        return False
    
    # 确保当前目录有crypto_utils.py
    if not crypto_utils_current.exists():
        print_warning(f"本地目录中未找到crypto_utils.py，正在复制...")
        try:
            shutil.copy(crypto_utils_remote, crypto_utils_current)
            print_success(f"已复制crypto_utils.py到: {crypto_utils_current}")
        except Exception as e:
            print_error(f"复制crypto_utils.py失败: {e}")
            return False
    
    # 测试导入
    try:
        sys.path.append(str(current_dir))
        sys.path.append(str(remote_dir))
        
        # 测试crypto_utils导入
        from crypto_utils import encrypt_text, decrypt_text
        print_success("成功导入加密模块!")
        return True
    except ImportError as e:
        print_error(f"导入加密模块失败: {e}")
        return False

def check_gui_tool():
    print_header("检查GUI工具...")
    
    # 获取路径
    current_dir = Path(__file__).parent.absolute()
    gui_path = current_dir / "markdown_decrypt_gui.py"
    
    if not gui_path.exists():
        print_error(f"未找到GUI工具: {gui_path}")
        return False
    
    # 确保GUI文件有执行权限
    try:
        gui_path.chmod(gui_path.stat().st_mode | 0o111)  # 添加执行权限
        print_success(f"已设置GUI工具执行权限")
    except Exception as e:
        print_warning(f"设置执行权限失败(非致命错误): {e}")
    
    return True

def launch_gui():
    print_header("启动GUI解密工具...")
    
    # 获取路径
    current_dir = Path(__file__).parent.absolute()
    gui_path = current_dir / "markdown_decrypt_gui.py"
    
    try:
        # 先刷新UI提示信息
        sys.stdout.flush()
        
        # 启动GUI工具
        if os.name == 'nt':  # Windows
            subprocess.Popen([sys.executable, str(gui_path)])
        else:  # Linux/Mac
            subprocess.Popen([str(gui_path)])
        
        print_success("成功启动GUI工具")
        return True
    except Exception as e:
        print_error(f"启动GUI工具失败: {e}")
        print_warning("尝试备用启动方式...")
        
        try:
            subprocess.Popen([sys.executable, str(gui_path)])
            print_success("使用备用方式成功启动GUI工具")
            return True
        except Exception as e2:
            print_error(f"备用启动方式也失败: {e2}")
            return False

def main():
    print_header("Markdown文件安全查看器 - 启动程序")
    print("本程序将帮助您设置环境并启动GUI解密工具\n")
    
    # 步骤1: 安装依赖
    if not install_dependencies():
        print_error("依赖安装失败，程序无法继续")
        input("按Enter键退出...")
        return
    
    # 步骤2: 修复导入
    if not fix_imports():
        print_error("修复模块导入失败，程序可能无法正常工作")
        choice = input("是否继续尝试启动GUI工具? (y/n): ").lower()
        if choice != 'y':
            return
    
    # 步骤3: 检查GUI工具
    if not check_gui_tool():
        print_error("无法找到GUI工具，请确保markdown_decrypt_gui.py文件存在")
        input("按Enter键退出...")
        return
    
    # 步骤4: 启动GUI
    if launch_gui():
        print_success("启动完成! GUI工具已在新窗口中打开")
    else:
        print_error("启动GUI工具失败")
        print_warning("请尝试手动运行: python markdown_decrypt_gui.py")
    
    # 提示环境变量设置
    env_key = os.environ.get('MARKDOWN_ENCRYPT_KEY')
    if not env_key:
        print_warning("\n未检测到环境变量MARKDOWN_ENCRYPT_KEY")
        print("您可以设置此环境变量以使用自定义密钥:")
        print("  export MARKDOWN_ENCRYPT_KEY=\"your-secret-key-here\"")
    else:
        print_success(f"\n检测到环境变量密钥: {env_key[0]}{'*'*(len(env_key)-2)}{env_key[-1]}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n操作已取消")
    except Exception as e:
        print_error(f"\n程序发生错误: {e}")
        input("按Enter键退出...")
