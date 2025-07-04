# RDK X5 Intelligent Office Assistant

#### Description
An intelligent office assistant system based on RDK X5 development board, providing multi-model collaborative document processing and task management functions. The project includes two core modules:
- **Intelligent Document Processing System** (`layout_llm_web_rdk`) - PDF document intelligent parsing, layout analysis and Markdown conversion
- **Todo Management System** (`todo_rdk`) - Modern task management and scheduling tool

#### Software Architecture

```
RDK X5 Intelligent Office Assistant
├── layout_llm_web_rdk/          # Intelligent Document Processing System
│   ├── app.py                   # Flask Web Service Main Program
│   ├── llm.py                   # LLM Model Interface (Ollama Support)
│   ├── layout_process/          # Document Processing Core Module
│   │   ├── pipeline.py          # Complete Processing Pipeline
│   │   ├── layout_analyzer/     # Layout Analysis (RapidLayout-based)
│   │   ├── ppocr/              # OCR Text Recognition (PaddleOCR-based)
│   │   └── RapidLayout/        # Layout Analysis Engine
│   └── remote/                 # Document Encryption and Remote Processing
└── todo_rdk/                   # Todo Management System
    ├── backend/                # Flask Backend API
    │   ├── app.py             # Web Server
    │   └── database.py        # SQLite Database Operations
    └── frontend/              # Modern Web Frontend
        ├── index.html         # Main Interface
        ├── css/style.css      # Stylesheets
        └── js/               # JavaScript Logic
```

#### Features

**Intelligent Document Processing System:**
- 📄 Automatic PDF document parsing and layout analysis
- 🔍 Intelligent OCR text recognition and extraction
- 📋 Automatic generation of structured Markdown documents
- 🎯 Support for complex layout recognition including charts, formulas, tables
- 🔐 Document content encryption and secure processing
- 🌐 Web interface for batch processing and real-time preview

**Todo Management System:**
- ✅ Task creation, editing and completion status management
- 📅 Calendar view and list view switching
- 🏷️ Task categorization and priority settings
- ⏰ Due date reminders and time management
- 🎨 Modern UI design with theme switching support
- 📱 Responsive design with mobile device support

#### Installation

1. **Environment Setup**
   ```bash
   # Python 3.8+ environment
   python --version
   
   # Install system dependencies (Ubuntu/Debian)
   sudo apt-get update
   sudo apt-get install python3-pip python3-venv
   ```

2. **Intelligent Document Processing System Installation**
   ```bash
   cd layout_llm_web_rdk
   pip install -r requirements.txt
   
   # Install Ollama (optional, for LLM functionality)
   curl -fsSL https://ollama.ai/install.sh | sh
   ollama pull qwen2.5:1.5b
   ```


#### Instructions

**Intelligent Document Processing System:**

1. **Start Web Service**
   ```bash
   cd layout_llm_web_rdk
   python app.py
   ```
   Access `http://localhost:5001` to enter the web interface

2. **Document Processing Workflow**
   - Upload PDF documents to the system
   - System automatically performs layout analysis and OCR recognition
   - Generate structured Markdown documents
   - Support batch processing and result downloading

3. **Command Line Usage**
   ```bash
   # Single document processing
   cd layout_process
   python pipeline.py --input demo.pdf --output results/
   
   # Batch processing
   python remote/exe.py
   ```

**Todo Management System:**

1. **Start Service**
   ```bash
   cd todo_rdk
   python backend/app.py
   ```
   Access `http://localhost:4999` to use the task management interface

2. **Feature Usage**
   - Create new tasks: Click "Add New Task" button
   - Task management: Set title, description, priority and due date
   - View switching: Switch between list view and calendar view
   - Theme switching: Support light/dark theme
