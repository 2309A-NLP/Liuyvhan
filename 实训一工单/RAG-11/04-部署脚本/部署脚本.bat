@echo off
chcp 65001 >nul
title RAG-工单11 部署脚本
setlocal enabledelayedexpansion

echo ==============================================
echo    RAG-工单11 启动脚本
echo    Embedding模型微调 + 多模态图片语义解析
echo ==============================================
echo.

:: ====== 第1步：检查Docker容器 ======
echo [1/7] 检查 Docker 容器...
docker ps --format "{{.Names}}" 2>nul | findstr "rag-redis" >nul
if errorlevel 1 (
    echo   [!] rag-redis 未运行，请先启动 Docker 容器
    echo   启动命令: docker start rag-redis milvus-etcd milvus-minio milvus-standalone
    pause
    exit /b 1
) else (
    echo   [OK] rag-redis 运行中
)

:: 检查 Milvus
docker ps --format "{{.Names}}" 2>nul | findstr "milvus-standalone" >nul
if errorlevel 1 (
    echo   [!] milvus-standalone 未运行
    pause
    exit /b 1
) else (
    echo   [OK] milvus-standalone 运行中
)

:: ====== 第2步：切换到项目目录 ======
echo [2/7] 切换到项目目录...
cd /d "C:\Users\刘禹含\Desktop\RAG-工单11"
if errorlevel 1 (
    echo   [!] 目录不存在: C:\Users\刘禹含\Desktop\RAG-工单11
    pause
    exit /b 1
)
echo   [OK] %cd%

:: ====== 第3步：检查 Conda 环境 ======
echo [3/7] 检查 Python 环境...
set PYTHON=D:\Anaconda\envs\RAG\python.exe
if not exist "%PYTHON%" (
    echo   [!] 未找到: %PYTHON%
    echo   请修改此脚本中的 PYTHON 路径
    pause
    exit /b 1
)
echo   [OK] Python: %PYTHON%
%PYTHON% --version

:: ====== 第4步：检查 .env 配置文件 ======
echo [4/7] 检查 .env 配置...
if not exist ".env" (
    echo   [!] .env 文件不存在
    pause
    exit /b 1
)
echo   [OK] .env 已找到

:: ====== 第5步：检查本地模型缓存 ======
echo [5/7] 检查模型缓存...

:: 检查 finetuned-bge-zh 微调模型
if exist "data\models\finetuned-bge-zh\" (
    echo   [OK] 微调Embedding模型: data\models\finetuned-bge-zh\
) else (
    echo   [!] 微调模型未找到: data\models\finetuned-bge-zh\
    echo   请确认模型已下载或训练
    pause
    exit /b 1
)

:: 检查 Reranker 模型
set RERANKER_DIR=C:\Users\刘禹含\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3
if exist "%RERANKER_DIR%" (
    echo   [OK] Reranker 模型已缓存
)

:: 检查 CLIP 模型
if exist "C:\models\clip-vit-base-patch32\" (
    echo   [OK] CLIP 模型: C:\models\clip-vit-base-patch32\
) else (
    echo   [!] CLIP 模型未找到，将使用在线模式
)

:: 检查 sentence-transformers (用于RAGAS评估)
%PYTHON% -c "import sentence_transformers; print('  [OK] sentence-transformers:', sentence_transformers.__version__)" 2>nul
if errorlevel 1 (
    echo   [!] sentence-transformers 未安装
    echo   安装命令: pip install sentence-transformers
)

:: ====== 第6步：启动 API 服务 ======
echo [6/7] 启动 uvicorn API 服务...
echo   端口: 8000
echo   模型: finetuned-bge-zh (微调)
echo   多模态: CLIP + VLM
echo   集合: prospectus_chunks_ticket04_multimodal

:: 确保HF离线模式
set HF_HUB_OFFLINE=1

start /B "" "%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info

if errorlevel 1 (
    echo   [!] uvicorn 启动失败
    pause
    exit /b 1
)
echo   [OK] uvicorn 已在后台启动

:: ====== 第7步：等待服务就绪 ======
echo [7/7] 等待 API 服务就绪...
set RETRY_COUNT=0
:RETRY
timeout /t 3 /nobreak >nul
curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    set /a RETRY_COUNT+=1
    if !RETRY_COUNT! geq 10 (
        echo   [!] 服务启动超时，请检查日志
        pause
        exit /b 1
    )
    echo   等待服务就绪... (第!RETRY_COUNT!次)
    goto RETRY
)
echo   [OK] API 服务已就绪
echo.
echo ==============================================
echo    启动完成！
echo    API: http://127.0.0.1:8000
echo    文档: http://127.0.0.1:8000/docs
echo    健康检查: http://127.0.0.1:8000/health
echo ==============================================
echo.
echo 可用端点:
echo   POST /chat/rag     - RAG 问答
echo   POST /chat/llm     - 纯LLM 问答
echo   POST /documents/upload - 上传PDF
echo   POST /documents/index  - 索引文档
echo   POST /evaluation/run   - 运行RAGAS评估
echo.
pause
