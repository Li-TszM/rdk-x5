# RDK X5 智能办公助手

#### 介绍
基于RDK X5开发板的智能办公助手系统，提供多模型协同的文档处理和任务管理功能。项目包含两个核心模块：
- **智能文档处理系统** (`layout_llm_web_rdk`) - PDF文档智能解析、版面分析和Markdown转换
- **待办事项管理系统** (`todo_rdk`) - 现代化的任务管理和日程安排工具

#### 软件架构

```
RDK X5 智能办公助手
├── layout_llm_web_rdk/          # 智能文档处理系统
│   ├── app.py                   # Flask Web服务主程序
│   ├── llm.py                   # LLM模型接口（支持Ollama）
│   ├── layout_process/          # 文档处理核心模块
│   │   ├── pipeline.py          # 完整处理流水线
│   │   ├── layout_analyzer/     # 版面分析（基于RapidLayout）
│   │   ├── ppocr/              # OCR文字识别（基于PaddleOCR）
│   │   └── RapidLayout/        # 版面分析引擎
│   └── remote/                 # 文档加密和远程处理
└── todo_rdk/                   # 待办事项管理系统
    ├── backend/                # Flask后端API
    │   ├── app.py             # Web服务器
    │   └── database.py        # SQLite数据库操作
    └── frontend/              # 现代化Web前端
        ├── index.html         # 主界面
        ├── css/style.css      # 样式表
        └── js/               # JavaScript逻辑
```

#### 安装教程

1. **环境准备**
   ```bash
   # Python 3.8+ 环境
   python --version
   
   # 安装系统依赖（Ubuntu/Debian）
   sudo apt-get update
   sudo apt-get install python3-pip python3-venv
   ```

2. **智能文档处理系统安装**
   ```bash
   cd layout_llm_web_rdk
   pip install -r requirements.txt
   
   # 安装Ollama（可选，用于LLM功能）
   curl -fsSL https://ollama.ai/install.sh | sh
   ollama pull qwen2.5:1.5b
   ```


#### 使用说明

**智能文档处理系统：**

1. **启动Web服务**
   ```bash
   cd layout_llm_web_rdk
   python app.py
   ```
   访问 `http://localhost:5001` 进入Web界面

2. **文档处理流程**
   - 上传PDF文档到系统
   - 系统自动进行版面分析和OCR识别
   - 生成结构化Markdown文档
   - 支持批量处理和结果下载


**待办事项管理系统：**

1. **启动服务**
   ```bash
   cd todo_rdk
   python backend/app.py
   ```
   访问 `http://localhost:4999` 使用任务管理界面

2. **功能使用**
   - 创建新任务：点击"添加新任务"按钮
   - 任务管理：设置标题、描述、优先级和截止日期
   - 视图切换：在列表视图和日历视图间切换
   - 主题切换：支持亮色/暗色主题





