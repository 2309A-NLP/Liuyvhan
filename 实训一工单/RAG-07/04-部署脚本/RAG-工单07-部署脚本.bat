@echo off
chcp 65001 >nul
title RAG-工单07 启动脚本 (CCF竞赛)
setlocal enabledelayedexpansion

echo ===== RAG-工单07 部署启动脚本 (CCF竞赛) =====
echo.

REM 第1步：检查 Docker 容器
echo [1/7] 检查 Docker 容器...
docker ps --format "{{.Names}}" 2>nul | findstr "rag-redis" >nul
if %errorlevel% neq 0 (
    echo   [WARNING] rag-redis 未运行！请先启动 Docker 容器。
    echo   执行: cd 项目目录 ^&^& docker-compose up -d
) else (
    echo   [OK] rag-redis 运行中
)
docker ps --format "{{.Names}}" 2>nul | findstr "milvus-etcd" >nul
if %errorlevel% neq 0 (
    echo   [WARNING] milvus-etcd 未运行！
) else (
    echo   [OK] milvus-etcd 运行中
)
docker ps --format "{{.Names}}" 2>nul | findstr "milvus-minio" >nul
if %errorlevel% neq 0 (
    echo   [WARNING] milvus-minio 未运行！
) else (
    echo   [OK] milvus-minio 运行中
)
docker ps --format "{{.Names}}" 2>nul | findstr "milvus-standalone" >nul
if %errorlevel% neq 0 (
    echo   [WARNING] milvus-standalone 未运行！
) else (
    echo   [OK] milvus-standalone 运行中
)
echo.

REM 第2步：cd 到项目目录
echo [2/7] 切换到项目目录...
cd /d "C:\Users\刘禹含\Desktop\RAG-工单07"
echo   [OK] 当前目录: %cd%
echo.

REM 第3步：检查 Conda Python
echo [3/7] 检查 Python 环境...
set PYTHON=D:\Anaconda\envs\RAG\python.exe
if not exist "%PYTHON%" (
    echo   [ERROR] 未找到 Python: %PYTHON%
    echo   请修改本脚本中的 PYTHON 路径为你的 Conda 环境路径。
    pause
    exit /b 1
)
echo   [OK] Python: %PYTHON%
echo   [OK] Python 版本:
"%PYTHON%" --version
echo.

REM 第4步：检查 .env 配置
echo [4/7] 检查 .env 配置文件...
if not exist ".env" (
    echo   [ERROR] .env 文件不存在！
    echo   请复制 .env.example 为 .env 并填写配置。
    pause
    exit /b 1
)
echo   [OK] .env 已存在
echo   [关键配置检查]
findstr "LLM_API_KEY" .env | findstr "sk-" >nul
if %errorlevel% equ 0 (
    echo     [OK] LLM_API_KEY 已配置
) else (
    echo     [WARNING] LLM_API_KEY 未配置！
)
findstr "EMBEDDING_MODEL" .env >nul
if %errorlevel% equ 0 (
    echo     [OK] EMBEDDING_MODEL 已配置
)
findstr "ENABLE_RERANKER" .env >nul
if %errorlevel% equ 0 (
    echo     [OK] ENABLE_RERANKER 已配置 (当前=false)
)
findstr "ENABLE_QUERY_REWRITE" .env >nul
if %errorlevel% equ 0 (
    echo     [OK] Query三开关已配置
)
findstr "ENABLE_MULTIMODAL_IMAGE_PARSING" .env >nul
if %errorlevel% equ 0 (
    echo     [OK] 多模态开关已配置
)
findstr "REDIS_URL" .env >nul
if %errorlevel% equ 0 (
    echo     [OK] Redis缓存已配置
)
echo.

REM 第5步：检查模型缓存
echo [5/7] 检查本地模型缓存...
set HF_CACHE=%USERPROFILE%\.cache\huggingface\hub
if exist "!HF_CACHE!\models--BAAI--bge-reranker-v2-m3" (
    echo   [OK] bge-reranker-v2-m3 已缓存
) else (
    echo   [INFO] bge-reranker-v2-m3 未缓存（当前关闭状态，无需）
)
echo   [OK] synonym_dict.json 不需要缓存（内置文本文件）
echo.

REM 第6步：启动 uvicorn
echo [6/7] 启动 RAG 服务...
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
echo   [INFO] HF_HUB_OFFLINE=1 (离线模式)
echo   [INFO] 启动端口: 8000
set LOG_FILE=server_output.log
start /B "" "%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 > "%LOG_FILE%" 2>&1
echo   [OK] uvicorn 已在后台启动 (PID: !ERRORLEVEL!)
echo.

REM 第7步：健康检查
echo [7/7] 健康检查（等待服务就绪）...
set RETRIES=0
:CHECK
timeout /t 3 /nobreak >nul
set /a RETRIES+=1
if !RETRIES! gtr 10 (
    echo   [ERROR] 服务未在30秒内就绪，请检查 %LOG_FILE%
    exit /b 1
)
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] 服务已就绪！
    echo   [URL] http://localhost:8000/docs
) else (
    goto CHECK
)
echo.
echo ===== 启动完成！=====
echo.
echo 快速测试:
echo   curl http://localhost:8000/health
echo   curl -X POST http://localhost:8000/chat/rag -H "Content-Type: application/json" -d "{\"question\":\"中国太保2021年度的集团营业收入和净利润分别是多少？\"}"
echo.
echo 查看服务日志:
echo   type server_output.log
echo.
pause
