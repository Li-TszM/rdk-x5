#!/usr/bin/env python
# GUI版Markdown解密工具 - 支持选择不同的加密协议
# 依            # 读取加密内容
import os
import sys
import json
import base64
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QTextEdit, QFileDialog, 
    QGroupBox, QCheckBox, QProgressBar, QMessageBox, QRadioButton,
    QComboBox, QStatusBar, QTabWidget, QSplitter
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QTextCursor

# 确保可以导入加密模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'remote'))

try:
    from remote.crypto_utils import (
        decrypt_text_protocol1, decrypt_text_protocol2, 
        decrypt_text_protocol3, decrypt_text
    )
except ImportError:
    try:
        from crypto_utils import (
            decrypt_text_protocol1, decrypt_text_protocol2, 
            decrypt_text_protocol3, decrypt_text
        )
    except ImportError:
        def show_error_and_exit():
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                None, 
                "错误", 
                "无法导入加密模块。请确保 crypto_utils.py 在当前目录或 'remote' 子目录中。",
                QMessageBox.Ok
            )
            sys.exit(1)
        show_error_and_exit()

# 解密工作线程 - 避免UI阻塞
class DecryptWorker(QThread):
    # 定义信号
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str, bool)  # 结果, 是否成功
    error_signal = pyqtSignal(str)
    
    def __init__(self, file_path, key, protocol=0):
        super().__init__()
        self.file_path = file_path
        self.key = key
        self.protocol = protocol  # 0=自动, 1/2/3=具体协议
    
    def run(self):
        try:
            # 读取加密内容
            with open(self.file_path, 'r', encoding='utf-8') as f:
                encrypted_content = f.read()
            
            self.progress_signal.emit(10)  # 读取文件完成
            
            # 逐一尝试所有解密方法
            # 1. 首先尝试使用内置的统一解密函数
            try:
                self.progress_signal.emit(25)
                plain_text = decrypt_text(encrypted_content, self.key)
                self.progress_signal.emit(100)
                self.finished_signal.emit(plain_text, True)
                return
            except Exception as e:
                self.progress_signal.emit(35)
                # 继续尝试其他方法
            
            # 2. 尝试解析JSON格式并根据协议信息解密
            try:
                self.progress_signal.emit(40)
                data = json.loads(encrypted_content)
                protocol = data.get("metadata", {}).get("protocol", 1)
                
                if protocol == 1:
                    plain_text = decrypt_text_protocol1(data.get("data", encrypted_content), self.key)
                    self.progress_signal.emit(100)
                    self.finished_signal.emit(plain_text, True)
                    return
                elif protocol == 2:
                    plain_text = decrypt_text_protocol2(encrypted_content, self.key)
                    self.progress_signal.emit(100)
                    self.finished_signal.emit(plain_text, True)
                    return
                elif protocol == 3:
                    plain_text = decrypt_text_protocol3(encrypted_content, self.key)
                    self.progress_signal.emit(100)
                    self.finished_signal.emit(plain_text, True)
                    return
            except Exception as e:
                self.progress_signal.emit(50)
                # 继续尝试
            
            # 解密失败但非JSON错误
            try:
                self.progress_signal.emit(50)
                plain_text = decrypt_text_protocol1(encrypted_content, self.key)
                self.progress_signal.emit(100)
                self.finished_signal.emit(plain_text, True)
                return
            except Exception as e:
                self.progress_signal.emit(60)
                # 继续尝试协议2
                try:
                    self.progress_signal.emit(70)
                    plain_text = decrypt_text_protocol2(encrypted_content, self.key)
                    self.progress_signal.emit(100)
                    self.finished_signal.emit(plain_text, True)
                    return
                except Exception as e:
                    self.progress_signal.emit(80)
                    # 最后尝试协议3
                    try:
                        self.progress_signal.emit(90)
                        plain_text = decrypt_text_protocol3(encrypted_content, self.key)
                        self.progress_signal.emit(100)
                        self.finished_signal.emit(plain_text, True)
                        return
                    except Exception as e:
                        # 所有协议都失败
                        raise Exception("所有解密协议均尝试失败，请检查密钥是否正确或文件是否损坏")
            
        except Exception as e:
            self.error_signal.emit(f"解密失败: {str(e)}")
            self.finished_signal.emit("", False)


class MarkdownDecryptGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        
    def initUI(self):
        # 窗口设置
        self.setWindowTitle('Markdown文档安全查看器')
        self.setGeometry(100, 100, 900, 700)  # 左上角坐标, 宽度, 高度
        
        # 创建中央组件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 创建文件选择框
        file_group = QGroupBox("文件选择")
        file_layout = QHBoxLayout()
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择加密的Markdown文件...")
        self.file_path_edit.setReadOnly(True)
        file_layout.addWidget(self.file_path_edit)
        
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self.browse_file)
        file_layout.addWidget(self.browse_button)
        
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # 创建密钥输入框
        key_group = QGroupBox("解密密钥")
        key_layout = QVBoxLayout()
        
        key_input_layout = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("输入解密密钥...")
        self.key_edit.setEchoMode(QLineEdit.Password)  # 密码模式
        key_input_layout.addWidget(self.key_edit)
        
        self.show_key_checkbox = QCheckBox("显示密钥")
        self.show_key_checkbox.stateChanged.connect(self.toggle_key_visibility)
        key_input_layout.addWidget(self.show_key_checkbox)
        
        key_layout.addLayout(key_input_layout)
        
        # 环境变量选项
        env_key_layout = QHBoxLayout()
        self.use_env_checkbox = QCheckBox("使用环境变量密钥")
        self.use_env_checkbox.setChecked(True)
        self.use_env_checkbox.stateChanged.connect(self.toggle_key_input)
        env_key_layout.addWidget(self.use_env_checkbox)
        
        env_var_label = QLabel("(环境变量: MARKDOWN_ENCRYPT_KEY)")
        env_var_label.setStyleSheet("color: gray;")
        env_key_layout.addWidget(env_var_label)
        env_key_layout.addStretch()
        
        key_layout.addLayout(env_key_layout)
        key_group.setLayout(key_layout)
        main_layout.addWidget(key_group)
        
        # 自动检测协议说明
        info_label = QLabel("系统将自动检测并尝试所有解密协议，无需手动选择")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(info_label)
        
        # 创建操作按钮
        action_layout = QHBoxLayout()
        
        self.decrypt_button = QPushButton("解密文档")
        self.decrypt_button.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white; padding: 6px;")
        self.decrypt_button.clicked.connect(self.decrypt_file)
        action_layout.addWidget(self.decrypt_button)
        
        self.save_button = QPushButton("保存解密内容")
        self.save_button.setEnabled(False)  # 初始禁用
        self.save_button.clicked.connect(self.save_decrypted)
        action_layout.addWidget(self.save_button)
        
        main_layout.addLayout(action_layout)
        
        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        # 创建内容显示区
        content_group = QGroupBox("解密内容")
        content_layout = QVBoxLayout()
        
        self.content_edit = QTextEdit()
        self.content_edit.setReadOnly(True)
        self.content_edit.setPlaceholderText("解密后的内容将显示在这里...")
        self.content_edit.setFont(QFont("Consolas", 10))
        content_layout.addWidget(self.content_edit)
        
        content_group.setLayout(content_layout)
        main_layout.addWidget(content_group)
        
        # 创建状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪")
        
        # 存储解密后的内容
        self.decrypted_content = ""
        
        # 检查并显示环境变量密钥信息
        self.check_env_key()
        self.toggle_key_input()
        
    def browse_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择加密的Markdown文件", "", 
            "Markdown Files (*.md);;All Files (*)", 
            options=options
        )
        
        if file_path:
            self.file_path_edit.setText(file_path)
            self.statusBar.showMessage(f"已选择文件: {file_path}")
    
    def check_env_key(self):
        env_key = os.environ.get('MARKDOWN_ENCRYPT_KEY')
        if env_key:
            key_preview = f"{env_key[0]}{'*' * (len(env_key)-2)}{env_key[-1]}" if len(env_key) > 2 else "**"
            self.statusBar.showMessage(f"已检测到环境变量密钥: {key_preview}")
        else:
            self.statusBar.showMessage("未检测到环境变量密钥，请手动输入")
            self.use_env_checkbox.setChecked(False)
    
    def toggle_key_visibility(self, state):
        if state == Qt.Checked:
            self.key_edit.setEchoMode(QLineEdit.Normal)
        else:
            self.key_edit.setEchoMode(QLineEdit.Password)
    
    def toggle_key_input(self):
        self.key_edit.setEnabled(not self.use_env_checkbox.isChecked())
        if self.use_env_checkbox.isChecked():
            self.key_edit.setPlaceholderText("使用环境变量中的密钥...")
        else:
            self.key_edit.setPlaceholderText("输入解密密钥...")
    
    def get_key(self):
        """获取用户指定的密钥"""
        if self.use_env_checkbox.isChecked():
            key = os.environ.get('MARKDOWN_ENCRYPT_KEY', 'default-strong-key-1234567890')
            return key
        else:
            user_key = self.key_edit.text()
            if not user_key:
                QMessageBox.warning(self, "警告", "请输入解密密钥！")
                return None
            return user_key
    
    def decrypt_file(self):
        file_path = self.file_path_edit.text()
        if not file_path:
            QMessageBox.warning(self, "警告", "请先选择一个文件！")
            return
        
        key = self.get_key()
        if not key:
            return
        
        # 使用自动检测模式
        protocol = 0  # 自动检测协议
        
        # 禁用UI元素
        self.decrypt_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.statusBar.showMessage("正在解密...")
        
        # 创建并运行工作线程
        self.worker = DecryptWorker(file_path, key, protocol)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.handle_result)
        self.worker.error_signal.connect(self.handle_error)
        self.worker.start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        
        # 更新状态栏信息
        if value < 25:
            self.statusBar.showMessage("正在解析加密文件...")
        elif value < 50:
            self.statusBar.showMessage("尝试自动检测加密协议...")
        elif value < 75:
            self.statusBar.showMessage("正在尝试不同解密方法...")
        elif value < 100:
            self.statusBar.showMessage("解密即将完成...")
        else:
            self.statusBar.showMessage("解密成功！")
    
    def handle_result(self, content, success):
        # 重新启用UI元素
        self.decrypt_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        
        if success:
            self.content_edit.setText(content)
            self.decrypted_content = content
            self.save_button.setEnabled(True)
            self.progress_bar.setValue(100)  # 确保进度条显示100%
            self.statusBar.showMessage("解密成功！")
            
            # 查找文件中的元数据信息，但不显示协议信息
            try:
                # 检查内容前几行是否有文件信息
                lines = content.split('\n')
                file_info = []
                
                for line in lines[:10]:  # 前10行中查找文件信息
                    if "源文件" in line or "生成模型" in line or "生成时间" in line:
                        file_info.append(line)
                
                if file_info:
                    QMessageBox.information(self, "解密成功", 
                                           f"文件已成功解密！\n\n文件信息:\n{chr(10).join(file_info)}")
                else:
                    QMessageBox.information(self, "解密成功", "文件已成功解密！")
            except:
                QMessageBox.information(self, "解密成功", "文件已成功解密！")
        else:
            self.statusBar.showMessage("解密失败！")
            self.save_button.setEnabled(False)
    
    def handle_error(self, error_msg):
        # 简化错误信息，不显示具体协议细节
        simplified_msg = error_msg
        if "所有解密协议均尝试失败" in error_msg:
            simplified_msg = "解密失败，请检查密钥是否正确或文件是否损坏。"
        
        QMessageBox.critical(self, "解密错误", simplified_msg)
        self.progress_bar.setValue(0)  # 出错时重置进度条
        self.statusBar.showMessage("解密失败，请检查密钥或文件格式")
    
    def save_decrypted(self):
        if not self.decrypted_content:
            QMessageBox.warning(self, "警告", "没有可保存的解密内容！")
            return
        
        options = QFileDialog.Options()
        file_path = self.file_path_edit.text()
        
        # 创建默认的保存文件名
        default_name = ""
        if file_path:
            dir_name = os.path.dirname(file_path)
            base_name = os.path.basename(file_path)
            name, ext = os.path.splitext(base_name)
            default_name = os.path.join(dir_name, f"{name}.decrypted{ext}")
        
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存解密内容", default_name,
            "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)", 
            options=options
        )
        
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(self.decrypted_content)
                self.statusBar.showMessage(f"已保存解密内容到: {save_path}")
                QMessageBox.information(self, "保存成功", f"解密内容已保存到:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "保存错误", f"保存解密内容时发生错误:\n{str(e)}")

def main():
    app = QApplication(sys.argv)
    # 设置应用程序样式
    app.setStyle('Fusion')
    window = MarkdownDecryptGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
