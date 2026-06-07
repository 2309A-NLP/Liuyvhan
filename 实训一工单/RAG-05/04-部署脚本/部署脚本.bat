@echo off
chcp 65001 >nul
title RAG-工单05 一键部署脚本 - Query理解优化 + 多轮会话
color 0F

echo =============================================
echo    RAG-工单05 部署脚本
echo    Query理解优化 + 多轮会话记忆 + 断点续传
echo =============================================
echo.

:: ===== 第1步: 检查 Docker 容器 =====
echo [1/7] 检查 Docker 容器...
docker ps --format "{{.Names}}" 2>nul | findstr "rag-redis" >nul
if %errorlevel% neq 0 (
    echo   [WARNING] rag-redis 未运行 - 请先启动 Docker 容器
    echo   请执行: docker start rag-redis milvus-etcd milvus-minio milvus-standalone
) else (
    echo   [OK] rag-redis 已运行
)
docker ps --format "{{.Names}}" 2>nul | findstr "milvus-standalone" >nul
if %errorlevel% neq 0 (
    echo   [WARNING] milvus-standalone 未运行
) else (
    echo   [OK] milvus-standalone 已运行
)
echo.

:: ===== 第2步: 进入项目目录 =====
echo [2/7] 进入项目目录...
cd /d "%~dp0"
echo   当前路径: %CD%
echo.

:: ===== 第3步: 检查 Python 环境 =====
echo [3/7] 检查 Python 环境...
set PYTHON=D:\Anaconda\envs\RAG\python.exe
if not exist "%PYTHON%" (
    echo   [WARNING] %PYTHON% 未找到
    echo   正在尝试系统默认 Python...
    where python >nul 2>nul
    if %errorlevel% neq 0 (
        echo   [ERROR] Python 未安装！请安装 Anaconda 或配置 Python 3.12+
        pause
        exit /b 1
    )
    set PYTHON=python
) else (
    echo   [OK] Python: %PYTHON%
)
echo.

:: ===== 第4步: 检查 .env 配置文件 =====
echo [4/7] 检查 .env 配置文件...
set ENV_FILE=%~dp0.env
if not exist "%ENV_FILE%" (
    echo   [ERROR] .env 文件未找到！
    echo   请从 .env.example 复制并配置:
    echo   copy .env.example .env
    pause
    exit /b 1
)
echo   [OK] .env 文件已找到

:: 检查关键配置项
findstr "LLM_API_KEY" "%ENV_FILE%" | findstr "sk-" >nul
if %errorlevel% neq 0 (
    echo   [WARNING] LLM_API_KEY 未配置或格式错误
) else (
    echo   [OK] LLM_API_KEY 已配置
)
findstr "MILVUS_URI" "%ENV_FILE%" | findstr "http" >nul
if %errorlevel% neq 0 (
    echo   [WARNING] MILVUS_URI 未配置
) else (
    echo   [OK] MILVUS_URI 已配置
)
echo.

:: ===== 第5步: 检查本地模型缓存 =====
echo [5/7] 检查本地模型缓存...
set RERANKER_DIR=C:\Users\刘禹含\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3
if exist "%RERANKER_DIR%" (
    echo   [OK] Reranker 模型已缓存: BAAI/bge-reranker-v2-m3
) else (
    echo   [WARNING] Reranker 模型未缓存，首次启动将自动下载
)
set CLIP_DIR=C:\models\clip-vit-base-patch32
if exist "%CLIP_DIR%" (
    echo   [OK] CLIP 模型已缓存: clip-vit-base-patch32
) else (
    echo   [WARNING] CLIP 模型未缓存
)
set EMBEDDING_DIR=D:\m3e\人工智能NLP专高２新增附件 m3e-base\m3e-base
if exist "%EMBEDDING_DIR%" (
    echo   [OK] Embedding 模型已缓存: m3e-base
) else (
    echo   [WARNING] Embedding 模型路径未找到（尝试从 HF Hub 在线加载）
)
echo.

:: ===== 第6步: 启动 API 服务 =====
echo [6/7] 启动 API 服务...
echo   端口: 8000
echo   模型: DeepSeek-V4-Flash (SiliconFlow)
echo   Query理解: 意图分类 + 改写 + 同义扩展 + 查询分解
echo   多轮会话: ConversationStore (10轮, TTL=1800s)
echo   断点续传: Checkpoint 已启用

:: 后台启动 uvicorn
start /B "" "%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
echo   Server starting...
echo.

:: ===== 第7步: 验证服务 =====
echo [7/7] 验证服务是否就绪...
set RETRIES=0
:CHECK
timeout /t 3 /nobreak >nul
curl -s http://localhost:8000/api/v1/health >nul 2>nul
if %errorlevel% equ 0 (
    echo   [OK] 服务已就绪！ http://localhost:8000
    echo   API 文档: http://localhost:8000/docs
    goto END
)
set /a RETRIES+=1
if %RETRIES% lss 6 goto CHECK

echo   [WARNING] 服务未在30秒内就绪，请检查日志
echo   手动检查: curl http://localhost:8000/api/v1/health
echo.

:END
echo.
echo =============================================
echo    部署完成
echo    接口列表:
echo      GET  /api/v1/health          — 健康检查
echo      POST /api/v1/chat/rag        — RAG问答（支持 conversation_id）
echo      POST /api/v1/chat/llm        — 纯LLM问答
echo      POST /api/v1/documents/upload — 上传PDF
echo      POST /api/v1/documents/index  — 构建索引
echo      POST /api/v1/evaluation/run   — 运行评估
echo      POST /api/v1/feedback         — 提交反馈
echo =============================================
pause
