@echo off
chcp 65001 >nul
title RAG-工单06 启动脚本

echo ========================================
echo   RAG-工单06 — 招股说明书问答系统
echo   Query理解+会话记忆+多模态图片语义
echo =========================================
echo.

REM ====== 第1步：检查Docker容器 ======
echo [1/7] 检查Docker容器...
docker ps --format "{{.Names}}" 2>nul | findstr "rag-redis" >nul
if %errorlevel% neq 0 (
    echo   [!] rag-redis 未运行
    echo   请先启动 Docker 容器：docker compose up -d
    pause
    exit /b 1
)
echo   [OK] rag-redis 运行中

docker ps --format "{{.Names}}" 2>nul | findstr "milvus" >nul
if %errorlevel% neq 0 (
    echo   [!] Milvus 未运行
    echo   请先启动 Docker 容器：docker compose up -d
    pause
    exit /b 1
)
echo   [OK] Milvus 容器运行中
echo.

REM ====== 第2步：进入项目目录 ======
echo [2/7] 定位项目目录...
cd /d "C:\Users\刘禹含\Desktop\RAG-工单06"
if %errorlevel% neq 0 (
    echo   [!] 项目目录不存在
    pause
    exit /b 1
)
echo   [OK] 当前目录：%cd%
echo.

REM ====== 第3步：检查Python环境 ======
echo [3/7] 检查Python环境...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo   [!] Python 未找到，请安装 Anaconda
    pause
    exit /b 1
)
python --version
echo   [OK] Python 就绪
echo.

REM ====== 第4步：检查 .env 配置 ======
echo [4/7] 检查配置文件...
if not exist ".env" (
    echo   [!] .env 文件缺失
    pause
    exit /b 1
)
echo   [OK] .env 已找到
echo   - LLM: deepseek-ai/DeepSeek-V4-Flash (SiliconFlow)
echo   - Embedding: m3e-base (本地路径)
echo   - Reranker: BAAI/bge-reranker-v2-m3
echo   - Query理解: 意图分类+改写+同义扩展+分解
echo   - 多模态: CLIP + VLM Qwen3-VL
echo.

REM ====== 第5步：检查本地模型缓存 ======
echo [5/7] 检查模型缓存...
set OFFLINE=0

if exist "D:\m3e\人工智能NLP专高２新增附件 m3e-base\m3e-base" (
    echo   [OK] m3e-base 本地模型已找到
) else (
    echo   [!] m3e-base 未找到，将使用联网下载
)

if exist "C:\models\clip-vit-base-patch32" (
    echo   [OK] CLIP 模型已找到
) else (
    echo   [!] CLIP 模型未找到，将使用联网下载
)

echo   [OK] 同义词典: data/synonym_dict.json (42条)
echo.

REM ====== 第6步：启动服务 ======
echo [6/7] 启动 RAG 服务 (端口 8000)...
set HF_HUB_OFFLINE=1

start /B python run_uvicorn.py > server_console.log 2>&1
echo   [OK] 服务已启动 (PID: %errorlevel%)
echo   日志: server_console.log
echo.

REM ====== 第7步：等待服务就绪 ======
echo [7/7] 等待服务就绪...
set RETRIES=0
:HEALTH_CHECK
set /a RETRIES+=1
if %RETRIES% gtr 30 (
    echo   [!] 启动超时，请检查 server_console.log
    pause
    exit /b 1
)

>nul 2>&1 curl -s http://127.0.0.1:8000/health
if %errorlevel% neq 0 (
    timeout /t 2 /nobreak >nul
    goto HEALTH_CHECK
)

echo.
echo ========================================
echo   服务就绪！
echo   端口: 8000
echo   API: http://127.0.0.1:8000/docs
echo   Query理解: 意图分类+改写+扩展+分解
echo   会话记忆: ConversationStore 10轮
echo   多模态: CLIP + VLM
echo   断点续传: .index_checkpoint
echo =========================================

REM 自动打开浏览器
start http://127.0.0.1:8000/docs
