from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, abort
import os
import subprocess
import threading
import time
import json
import shutil
import zipfile
import tempfile
from werkzeug.utils import secure_filename
import logging
import uuid
import signal
import glob
from operator import itemgetter

app = Flask(__name__)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "remote", "input")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "remote", "output")
PROCESS_DIARY_FOLDER = os.path.join(BASE_DIR, "process_diary")  # 添加日志文件夹
ALLOWED_EXTENSIONS = {'pdf'}
PROCESS_TIMEOUT = 600  # 处理超时时间(秒)
MAX_LOG_FILES = 10  # 最大保留日志文件数量

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(PROCESS_DIARY_FOLDER, exist_ok=True)  # 创建日志文件夹

# 存储活动任务
active_processes = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 首页
@app.route('/')
def index():
    return redirect(url_for('upload_page'))

# 上传文档页面
@app.route('/upload', methods=['GET', 'POST'])
def upload_page():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            return jsonify({'success': True, 'filename': filename})
        
        return jsonify({'success': False, 'error': '不支持的文件类型'}), 400
    
    # GET请求返回上传页面
    return render_template('upload.html')

# 处理文档页面
@app.route('/process')
def process_page():
    return render_template('process.html')

# 构建文件夹树结构的辅助函数
def build_folder_tree(folder_path, base_path=""):
    """
    递归构建文件夹树结构
    返回包含文件和子文件夹的字典
    """
    tree = {
        'name': os.path.basename(folder_path),
        'path': base_path,
        'files': [],
        'folders': []
    }
    
    try:
        items = sorted(os.listdir(folder_path))
        
        for item in items:
            item_path = os.path.join(folder_path, item)
            rel_path = os.path.join(base_path, item) if base_path else item
            
            if os.path.isfile(item_path):
                # 添加文件信息
                file_size = os.path.getsize(item_path)
                modified_time = time.ctime(os.path.getmtime(item_path))
                
                tree['files'].append({
                    'name': item,
                    'size': file_size,
                    'modified': modified_time,
                    'path': rel_path,
                    'subfolder': ""  # 将在flatten函数中正确设置
                })
            elif os.path.isdir(item_path):
                # 递归处理子文件夹
                subtree = build_folder_tree(item_path, rel_path)
                tree['folders'].append(subtree)
    
    except PermissionError:
        # 处理权限错误
        pass
    
    return tree

def has_files_recursive(tree):
    """
    递归检查树结构中是否有文件
    """
    if tree['files']:
        return True
    for subfolder in tree['folders']:
        if has_files_recursive(subfolder):
            return True
    return False

def flatten_files_with_structure(tree, all_files=None, current_path=""):
    """
    扁平化文件，但保留完整的文件夹路径信息
    """
    if all_files is None:
        all_files = []
    
    # 添加当前层级的文件
    for file_info in tree['files']:
        # 更新文件信息，包含完整的子文件夹路径
        file_copy = file_info.copy()
        if current_path:
            file_copy['subfolder'] = current_path
        else:
            file_copy['subfolder'] = ""
        all_files.append(file_copy)
    
    # 递归处理子文件夹
    for subfolder in tree['folders']:
        subfolder_path = os.path.join(current_path, subfolder['name']) if current_path else subfolder['name']
        flatten_files_with_structure(subfolder, all_files, subfolder_path)
    
    return all_files

# 下载结果页面
@app.route('/download')
def download_page():
    results = []
    
    if os.path.exists(OUTPUT_FOLDER):
        # 遍历输出文件夹下的所有内容（子文件夹和文件）
        for folder_name in sorted(os.listdir(OUTPUT_FOLDER)):
            folder_path = os.path.join(OUTPUT_FOLDER, folder_name)
            
            if os.path.isdir(folder_path):
                # 构建文件夹树结构
                folder_tree = build_folder_tree(folder_path, folder_name)
                
                # 检查是否有文件
                if has_files_recursive(folder_tree):
                    # 获取扁平化的文件列表，但保留完整的文件夹路径信息
                    all_files = flatten_files_with_structure(folder_tree)
                    
                    # 按修改时间排序，最新的文件在前面
                    all_files.sort(key=lambda x: os.path.getmtime(os.path.join(OUTPUT_FOLDER, x['path'])), reverse=True)
                    
                    results.append({
                        'folder': folder_name,
                        'files': all_files,
                        'tree': folder_tree  # 保留完整的树结构
                    })
    
    return render_template('download.html', results=results)

# API端点：获取上传的文件列表
@app.route('/api/files')
def get_files():
    uploads = []
    
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            if allowed_file(filename):
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                uploads.append({
                    'name': filename,
                    'size': os.path.getsize(file_path),
                    'modified': time.ctime(os.path.getmtime(file_path))
                })
    
    return jsonify({'uploads': uploads})

# API端点：获取输出文件夹结构
@app.route('/api/output')
def get_output():
    output = {}
    
    if os.path.exists(OUTPUT_FOLDER):
        for folder_name in os.listdir(OUTPUT_FOLDER):
            folder_path = os.path.join(OUTPUT_FOLDER, folder_name)
            
            if os.path.isdir(folder_path):
                output[folder_name] = []
                
                for file_name in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file_name)
                    
                    if os.path.isfile(file_path):
                        output[folder_name].append({
                            'name': file_name,
                            'size': os.path.getsize(file_path),
                            'modified': time.ctime(os.path.getmtime(file_path))
                        })
    
    return jsonify(output)

# 清理旧日志文件，只保留最新的N个
def cleanup_log_files():
    try:
        # 获取目录中所有日志文件
        log_files = glob.glob(os.path.join(PROCESS_DIARY_FOLDER, "process_output_*.txt"))
        
        # 如果文件数量超过限制
        if len(log_files) > MAX_LOG_FILES:
            # 获取文件及其修改时间
            file_times = [(f, os.path.getmtime(f)) for f in log_files]
            # 按修改时间排序（最新的在前）
            file_times.sort(key=itemgetter(1), reverse=True)
            
            # 删除旧文件
            for file_path, _ in file_times[MAX_LOG_FILES:]:
                try:
                    os.remove(file_path)
                    logger.info(f"已删除旧日志文件: {os.path.basename(file_path)}")
                except Exception as e:
                    logger.error(f"删除旧日志文件时出错: {e}")
    except Exception as e:
        logger.error(f"清理日志文件时出错: {e}")

# API端点：PDF处理
@app.route('/api/process', methods=['POST'])
def process_document():
    data = request.get_json()
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'success': False, 'error': '未提供文件名'}), 400
    
    input_file = os.path.join(UPLOAD_FOLDER, filename)
    
    if not os.path.exists(input_file):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    
    # 生成唯一进程ID
    process_id = str(uuid.uuid4())
    
    # 创建输出捕获文件 - 修改路径到新文件夹
    output_capture_file = os.path.join(PROCESS_DIARY_FOLDER, f"process_output_{process_id}.txt")
    
    # 清理旧日志文件
    cleanup_log_files()
    
    # 启动处理线程
    thread = threading.Thread(
        target=run_document_processing,
        args=(process_id, input_file, output_capture_file)
    )
    thread.start()
    
    return jsonify({
        'success': True,
        'process_id': process_id,
        'message': '处理任务已启动'
    })

# API端点：LLM处理
@app.route('/api/llm', methods=['POST'])
def process_llm():
    data = request.get_json()
    md_file = data.get('md_file')
    mode = data.get('mode')
    
    if not md_file or not mode:
        return jsonify({'success': False, 'error': '参数不完整'}), 400
    
    # 计算完整路径
    folder_name, file_name = md_file.split('/')
    input_file = os.path.join(OUTPUT_FOLDER, folder_name, file_name)
    
    if not os.path.exists(input_file):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    
    # 生成唯一进程ID
    process_id = str(uuid.uuid4())
    
    # 创建输出捕获文件 - 修改路径到新文件夹
    output_capture_file = os.path.join(PROCESS_DIARY_FOLDER, f"process_output_{process_id}.txt")
    
    # 清理旧日志文件
    cleanup_log_files()
    
    # 准备LLM处理参数
    llm_args = ['--input', input_file, '--mode', mode]
    
    # 如果是翻译模式，添加翻译方向
    if mode == 'translation':
        translation_direction = data.get('translation_direction', '2')
        llm_args.extend(['--translation_direction', translation_direction])
    
    # 启动处理线程
    thread = threading.Thread(
        target=run_llm_processing,
        args=(process_id, llm_args, output_capture_file)
    )
    thread.start()
    
    return jsonify({
        'success': True,
        'process_id': process_id,
        'message': 'LLM处理任务已启动'
    })

# API端点：获取进程列表
@app.route('/api/process')
def get_processes():
    processes = []
    
    for pid, process in active_processes.items():
        # 计算进程状态和进度
        status = process.get('status', 'unknown')
        
        # 获取文件名
        filename = os.path.basename(process.get('file_path', '未知文件'))
        
        # 获取任务类型
        task_type = process.get('task_type', 'unknown')
        
        processes.append({
            'id': pid,
            'filename': filename,
            'status': status,
            'progress': process.get('progress', 0),
            'start_time': process.get('start_time', 'unknown'),
            'type': task_type  # 添加任务类型
        })
    
    return jsonify(processes)

# API端点：获取进程状态
@app.route('/api/process/<process_id>')
def get_process_status(process_id):
    if process_id not in active_processes:
        return jsonify({'error': '进程不存在'}), 404
    
    process_info = active_processes[process_id]
    
    # 读取输出日志 - 修改路径到新文件夹
    output_capture_file = os.path.join(PROCESS_DIARY_FOLDER, f"process_output_{process_id}.txt")
    output_lines = []
    
    if os.path.exists(output_capture_file):
        with open(output_capture_file, 'r') as f:
            output_lines = f.readlines()
    
    return jsonify({
        'status': process_info.get('status', 'unknown'),
        'progress': process_info.get('progress', 0),
        'file_path': process_info.get('file_path', ''),
        'start_time': process_info.get('start_time', ''),
        'output': output_lines[-50:] if output_lines else []  # 返回最近的50行日志
    })

@app.route('/api/process/<process_id>/log')
def get_process_log(process_id):
    log_file = os.path.join(PROCESS_DIARY_FOLDER, f"process_output_{process_id}.txt")
    if not os.path.exists(log_file):
        return jsonify({'log': ''})
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    return jsonify({'log': content})

# API端点：取消进程
@app.route('/api/process/<process_id>', methods=['DELETE'])
def cancel_process(process_id):
    if process_id not in active_processes:
        return jsonify({'success': False, 'error': '进程不存在'}), 404
    
    process_info = active_processes[process_id]
    process_obj = process_info.get('process')
    
    if process_obj and process_obj.poll() is None:
        # 尝试终止进程
        try:
            os.kill(process_obj.pid, signal.SIGTERM)
            process_info['status'] = 'terminated'
            process_info['progress'] = 0
            
            return jsonify({'success': True, 'message': '进程已终止'})
        except Exception as e:
            logger.error(f"终止进程时出错: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    else:
        # 进程已经结束
        return jsonify({'success': True, 'message': '进程已经结束'})

# API端点：下载文件
@app.route('/api/download-file/<path:file_path>')
def download_file(file_path):
    full_path = os.path.join(OUTPUT_FOLDER, file_path)
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        abort(404)
    
    # 获取文件名
    filename = os.path.basename(full_path)
    
    return send_file(full_path, as_attachment=True, download_name=filename)

# API端点：下载文件夹（打包为zip）
@app.route('/api/download-folder/<folder>')
def download_folder(folder):
    folder_path = os.path.join(OUTPUT_FOLDER, folder)
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        abort(404)
    
    # 创建临时zip文件，使用tempfile确保文件在临时目录且唯一
    temp_dir = tempfile.gettempdir()
    temp_zip = tempfile.NamedTemporaryFile(
        delete=False, 
        suffix='.zip', 
        prefix=f'{secure_filename(folder)}_',
        dir=temp_dir
    )
    temp_zip.close()
    
    try:
        # 创建zip文件
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, folder_path)
                    zipf.write(file_path, arcname=arcname)
        
        zip_filename = f"{folder}.zip"
        
        logger.info(f"创建临时zip文件: {temp_zip.name}")
        
        # 直接发送文件，临时文件将由定期清理任务处理
        return send_file(
            temp_zip.name, 
            as_attachment=True, 
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        # 如果创建zip失败，立即清理临时文件
        try:
            os.unlink(temp_zip.name)
        except:
            pass
        logger.error(f"创建zip文件失败: {e}")
        abort(500)

# API端点：删除文件
@app.route('/api/delete-file/<path:file_path>', methods=['POST'])
def delete_file(file_path):
    full_path = os.path.join(OUTPUT_FOLDER, file_path)
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    
    try:
        os.remove(full_path)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"删除文件时出错: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API端点：删除文件夹
@app.route('/api/delete-folder/<folder>', methods=['POST'])
def delete_folder(folder):
    folder_path = os.path.join(OUTPUT_FOLDER, folder)
    
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return jsonify({'success': False, 'error': '文件夹不存在'}), 404
    
    try:
        shutil.rmtree(folder_path)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"删除文件夹时出错: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API端点：删除上传文件
@app.route('/api/delete-upload/<filename>', methods=['POST'])
def delete_upload(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    
    try:
        os.remove(file_path)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"删除上传文件时出错: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API端点：下载上传的文件
@app.route('/api/download-upload/<filename>')
def download_upload_file(filename):
    full_path = os.path.join(UPLOAD_FOLDER, filename)
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        abort(404)
    
    # 获取文件名
    filename = os.path.basename(full_path)
    
    return send_file(full_path, as_attachment=True, download_name=filename)

# 运行文档处理进程
def run_document_processing(process_id, input_file, output_capture_file):
    try:
        # 记录开始时间
        start_time = time.time()
        
        # 初始化进程信息
        active_processes[process_id] = {
            'status': 'running',
            'progress': 0,
            'file_path': input_file,
            'start_time': time.ctime(start_time),
            'task_type': 'pdf'  # 添加任务类型
        }
        
        # 打开输出捕获文件
        with open(output_capture_file, 'w') as output_file:
            # 创建子进程
            process = subprocess.Popen(
                ['python', os.path.join(BASE_DIR, 'remote', 'exe.py')],
                stdout=output_file,
                stderr=subprocess.STDOUT,
                env=dict(os.environ, PDF_FILE_PATH=input_file)
            )
            
            # 保存进程对象
            active_processes[process_id]['process'] = process
            
            # 基于pipeline步骤的智能进度更新
            try:
                # 定义pipeline的6个主要步骤和对应的进度范围
                pipeline_steps = {
                    "步骤1: 开始版面分析": 15,
                    "版面分析完成": 25,
                    "步骤2: 开始OCR识别": 30,
                    "OCR识别完成": 50,
                    "步骤3: 转换OCR格式": 55,
                    "OCR格式转换完成": 60,
                    "步骤4: 合并版面块和OCR结果": 65,
                    "合并完成": 75,
                    "步骤5: 文本框阅读顺序排序": 80,
                    "阅读顺序排序完成": 85,
                    "步骤6: 生成Markdown文档": 88,
                    "Markdown生成完成": 90,
                    "开始使用pipeline处理文档": 10,
                    "Pipeline处理失败": 0,
                    "流水线执行成功": 95,
                    "文档处理完成": 100
                }
                
                max_monitoring_time = PROCESS_TIMEOUT
                start_monitoring_time = time.time()
                last_progress = 0
                
                while time.time() - start_monitoring_time < max_monitoring_time:
                    # 检查进程是否仍在运行
                    if process.poll() is not None:
                        break
                    
                    # 读取当前输出并分析进度
                    output_file.flush()
                    try:
                        with open(output_capture_file, 'r', encoding='utf-8') as f:
                            logs = f.read()
                    except:
                        logs = ""
                    
                    # 根据日志内容确定当前进度
                    current_progress = last_progress
                    
                    # 检查各个步骤标志
                    for step_marker, progress_value in pipeline_steps.items():
                        if step_marker in logs and progress_value > current_progress:
                            current_progress = progress_value
                    
                    # 特殊处理：检查是否有具体的步骤完成信息
                    if "⏱️" in logs and "耗时:" in logs:
                        # 有步骤完成的计时信息，可能是某个步骤完成了
                        step_count = logs.count("⏱️")
                        if step_count > 0:
                            # 根据完成的步骤数量更新进度
                            estimated_progress = min(10 + step_count * 12, 85)
                            current_progress = max(current_progress, estimated_progress)
                    
                    # 检查是否有错误或失败信息
                    if "失败" in logs or "错误" in logs or "异常" in logs:
                        if "步骤" in logs and "失败" in logs:
                            # 某个步骤失败了，保持当前进度不变
                            pass
                    
                    # 更新进度（确保进度不后退）
                    if current_progress > last_progress:
                        active_processes[process_id]['progress'] = current_progress
                        last_progress = current_progress
                        logger.info(f"任务[{process_id}]进度更新到: {current_progress}%")
                    
                    # 如果已经达到95%以上，说明即将完成
                    if current_progress >= 95:
                        break
                    
                    # 等待间隔
                    time.sleep(3)
                
                # 等待进程完成或超时
                process.wait(timeout=PROCESS_TIMEOUT)
                
                # 检查进程状态
                if process.returncode == 0:
                    active_processes[process_id]['status'] = 'completed'
                    active_processes[process_id]['progress'] = 100
                    # 处理成功后删除原始PDF文件
                    try:
                        if os.path.exists(input_file):
                            os.remove(input_file)
                            logger.info(f"已删除原始PDF文件: {input_file}")
                    except Exception as e:
                        logger.error(f"删除原始PDF文件失败: {e}")
                else:
                    active_processes[process_id]['status'] = 'failed'
            except subprocess.TimeoutExpired:
                # 进程超时，尝试终止
                process.terminate()
                active_processes[process_id]['status'] = 'failed'
                with open(output_capture_file, 'a') as f:
                    f.write('处理超时，任务已终止\n')
    except Exception as e:
        logger.error(f"文档处理失败: {e}")
        active_processes[process_id]['status'] = 'failed'
        with open(output_capture_file, 'a') as f:
            f.write(f'处理失败: {str(e)}\n')

# 运行LLM处理进程
def run_llm_processing(process_id, llm_args, output_capture_file):
    try:
        # 记录开始时间
        start_time = time.time()
        
        # 提取任务类型
        mode = None
        for i, arg in enumerate(llm_args):
            if arg == "--mode" and i+1 < len(llm_args):
                mode = llm_args[i+1]
                break
        
        # 初始化进程信息
        active_processes[process_id] = {
            'status': 'running',
            'progress': 0,
            'file_path': llm_args[1],  # 输入文件路径
            'start_time': time.ctime(start_time),
            'task_type': mode  # 添加任务类型
        }
        
        # 打开输出捕获文件
        with open(output_capture_file, 'w') as output_file:
            # 创建子进程
            cmd = ['python', os.path.join(BASE_DIR, 'llm.py')] + llm_args
            process = subprocess.Popen(
                cmd,
                stdout=output_file,
                stderr=subprocess.STDOUT
            )
            
            # 保存进程对象
            active_processes[process_id]['process'] = process
            
            # 更新进度并检查日志
            try:
                total_steps = 20  # 增加检测步数，提高检测频率
                for step in range(1, total_steps + 1):
                    # 检查进程是否仍在运行
                    if process.poll() is not None:
                        break
                    
                    # 读取日志内容检查进度
                    output_file.flush()
                    with open(output_capture_file, 'r') as f:
                        logs = f.read()
                    
                    # 检查是否包含成功处理的关键信息
                    if "文档处理完成" in logs or "输出文件:" in logs:
                        active_processes[process_id]['status'] = 'completed'
                        active_processes[process_id]['progress'] = 100
                        logger.info(f"任务[{process_id}]已成功完成: 检测到成功完成关键字")
                        break
                    # 检查是否有文件保存成功的标志（这是最终确认）
                    elif "内容已保存到:" in logs:
                        active_processes[process_id]['status'] = 'completed'
                        active_processes[process_id]['progress'] = 100
                        logger.info(f"任务[{process_id}]已成功完成: 检测到文件保存成功")
                        break
                    
                    # 根据日志内容更新进度
                    if "大模型API调用成功" in logs and "回复长度:" in logs:
                        # API调用成功，设置为95%，等待文件写入
                        progress = 95
                    elif "大模型API调用成功" in logs:
                        progress = 85
                    elif "开始调用大模型API" in logs:
                        progress = 50
                    elif "成功读取markdown文件" in logs or "读取明文Markdown" in logs:
                        progress = 30
                    else:
                        # 更新进度 (普通步进)
                        progress = min(int(step * 85 / total_steps), 85)  # 最高到85%，为后续检测留空间
                    
                    active_processes[process_id]['progress'] = progress
                    
                    # 等待一段时间
                    time.sleep(3)  # 减少间隔，提高检测频率
                
                # 等待进程完成或超时
                process.wait(timeout=PROCESS_TIMEOUT)
                
                # 进程完成后，最后检查一次输出确认状态
                output_file.flush()
                with open(output_capture_file, 'r') as f:
                    logs = f.read()
                
                # 检查进程状态
                if process.returncode == 0:
                    # 检查是否包含成功处理的关键信息
                    if ("文档处理完成" in logs or "输出文件:" in logs) and "内容已保存到:" in logs:
                        # 最完整的成功标志：有处理完成标志和文件保存确认
                        active_processes[process_id]['status'] = 'completed'
                        active_processes[process_id]['progress'] = 100
                        logger.info(f"任务[{process_id}]已成功完成: 完整的成功标志")
                    elif "内容已保存到:" in logs:
                        # 至少有文件保存成功的标志
                        active_processes[process_id]['status'] = 'completed'
                        active_processes[process_id]['progress'] = 100
                        logger.info(f"任务[{process_id}]已成功完成: 检测到文件保存成功")
                    elif "文档处理完成" in logs or "输出文件:" in logs:
                        # 有处理完成标志
                        active_processes[process_id]['status'] = 'completed'
                        active_processes[process_id]['progress'] = 100
                        logger.info(f"任务[{process_id}]已成功完成: 检测到处理完成标志")
                    elif "大模型API调用成功" in logs and "回复长度:" in logs:
                        # API调用成功，可能文件写入还未完成日志输出
                        active_processes[process_id]['status'] = 'completed'
                        active_processes[process_id]['progress'] = 100
                        logger.info(f"任务[{process_id}]已成功完成: API调用成功且进程正常退出")
                    else:
                        # 进程正常退出但没有明确的成功标志
                        active_processes[process_id]['status'] = 'completed'
                        active_processes[process_id]['progress'] = 100
                        logger.warning(f"任务[{process_id}]进程正常退出但未找到明确成功标记，假设成功完成")
                else:
                    active_processes[process_id]['status'] = 'failed'
                    logger.error(f"任务[{process_id}]失败: 退出码 {process.returncode}")
            except subprocess.TimeoutExpired:
                # 进程超时，尝试终止
                process.terminate()
                active_processes[process_id]['status'] = 'failed'
                with open(output_capture_file, 'a') as f:
                    f.write('处理超时，任务已终止\n')
                logger.error(f"任务[{process_id}]超时，已终止")
    except Exception as e:
        logger.error(f"LLM处理失败: {e}")
        active_processes[process_id]['status'] = 'failed'
        with open(output_capture_file, 'a') as f:
            f.write(f'处理失败: {str(e)}\n')

# 清理超过24小时的进程数据和临时文件
def cleanup_old_processes():
    current_time = time.time()
    expired_ids = []
    
    for pid, process in active_processes.items():
        # 获取进程开始时间
        start_time_str = process.get('start_time', '')
        
        try:
            # 转换时间字符串为时间戳
            start_time = time.mktime(time.strptime(start_time_str))
            
            # 如果进程已经运行超过24小时
            if current_time - start_time > 86400:
                expired_ids.append(pid)
        except:
            # 如果时间解析失败，也标记为过期
            expired_ids.append(pid)
    
    # 删除过期的进程
    for pid in expired_ids:
        # 清理进程相关文件
        output_capture_file = os.path.join(BASE_DIR, f"process_output_{pid}.txt")
        if os.path.exists(output_capture_file):
            os.remove(output_capture_file)
        
        # 从活动进程字典中删除
        del active_processes[pid]
    
    # 清理临时zip文件（超过1小时的）
    cleanup_temp_zip_files()

def cleanup_temp_zip_files():
    """清理临时目录中超过1小时的zip文件"""
    try:
        temp_dir = tempfile.gettempdir()
        current_time = time.time()
        
        for filename in os.listdir(temp_dir):
            if filename.endswith('.zip'):
                file_path = os.path.join(temp_dir, filename)
                try:
                    # 检查文件修改时间
                    file_mtime = os.path.getmtime(file_path)
                    
                    # 如果文件超过1小时，删除它
                    if current_time - file_mtime > 3600:
                        # 简单检查是否是临时zip文件（包含下划线的通常是临时文件）
                        if '_' in filename or filename.count('.') > 1:
                            os.remove(file_path)
                            logger.info(f"清理过期临时zip文件: {file_path}")
                except Exception as e:
                    logger.warning(f"清理临时文件 {file_path} 时出错: {e}")
                    
    except Exception as e:
        logger.error(f"清理临时zip文件时出错: {e}")

# 启动定时清理任务
def start_cleanup_scheduler():
    cleanup_old_processes()
    threading.Timer(3600, start_cleanup_scheduler).start()  # 每小时运行一次

if __name__ == '__main__':
    # 启动清理调度器
    start_cleanup_scheduler()
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5001, debug=True)
