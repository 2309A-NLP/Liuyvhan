@echo off
chcp 65001 >nul
title RAG-工单10 CCF竞赛年报QA系统 部署脚本

:: ============================================================
:: RAG-工单10 部署脚本 — CCF竞赛年报QA系统
:: ============================================================

echo ═══════════════════════════════════════════
echo    RAG-工单10 部署脚本 — CCF竞赛年报QA系统
echo ═══════════════════════════════════════════
echo.

:: ---- 第1步：检查 Docker 容器 ----
echo [1/7] 检查 Docker 容器...
docker ps --format "{{.Names}}" | findstr "rag-redis" >nul
if %errorlevel% neq 0 (
    echo   [警告] rag-redis 未运行！请先启动 Docker 容器。
    echo   请运行: docker compose up -d
    pause
    exit /b 1
)
echo   √ rag-redis 运行中

docker ps --format "{{.Names}}" | findstr "milvus-standalone" >nul
if %errorlevel% neq 0 (
    echo   [警告] milvus-standalone 未运行！
    pause
    exit /b 1
)
echo   √ milvus-standalone 运行中
echo.

:: ---- 第2步：进入项目目录 ----
echo [2/7] 进入项目目录...
cd /d "C:\Users\刘禹含\Desktop\RAG-工单10"
if %errorlevel% neq 0 (
    echo   [失败] 无法进入项目目录
    pause
    exit /b 1
)
echo   √ 当前目录: %cd%
echo.

:: ---- 第3步：检查 Python ----
echo [3/7] 检查 Python 环境...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo   [失败] 未找到 Python，检查 Conda 环境...
    call conda activate RAG 2>nul
    if %errorlevel% neq 0 (
        echo   [失败] Conda RAG 环境不可用
        pause
        exit /b 1
    )
)
echo   √ Python: 
python --version
echo.

:: ---- 第4步：检查 .env 配置文件 ----
echo [4/7] 检查 .env 配置文件...
if not exist ".env" (
    echo   [失败] 未找到 .env 文件
    pause
    exit /b 1
)
echo   √ .env 文件存在
echo   - LLM: DeepSeek-V4-Flash (SiliconFlow)
echo   - Embedding: paraphrase-multilingual-MiniLM-L12-v2
echo   - Reranker: 已关闭 (ENABLE_RERANKER=false)
echo   - Redis缓存: 已开启
echo   - Query三开关: 全部开启
echo   - 多模态: CLIP + VLM 开启
echo   - Milvus集合: ccf_competition_chunks_20260609
echo.

:: ---- 第5步：检查本地模型缓存 ----
echo [5/7] 检查本地模型缓存...

set HF_HOME=%USERPROFILE%\.cache\huggingface

if exist "%USERPROFILE%\.cache\huggingface\hub\models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2" (
    echo   √ paraphrase-multilingual-MiniLM 已缓存
) else (
    echo   [警告] paraphrase-MiniLM 未在缓存目录中找到
    echo   尝试从本地路径加载...
)

if exist "C:\models\clip-vit-base-patch32" (
    echo   √ CLIP模型 已加载
) else (
    echo   [检查] CLIP模型将从 HuggingFace Hub 加载
)

echo.

:: ---- 第6步：启动 uvicorn ----
echo [6/7] 启动 uvicorn 服务...
echo   端口: 8000 (根据 .env 配置)

set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1

start /B python run_uvicorn.py > server_output.log 2>&1
if %errorlevel% neq 0 (
    echo   [失败] uvicorn 启动失败，尝试直接启动...
    start /B uvicorn main:app --host 0.0.0.0 --port 8000 > server_output.log 2>&1
)
echo   √ 服务已在后台启动
echo.

:: ---- 第7步：健康检查 ----
echo [7/7] 等待服务就绪（最多30秒）...
setlocal enabledelayedexpansion
set retries=0
:health_check
timeout /t 3 /nobreak >nul
curl -s http://127.0.0.1:8000/health >nul 2>nul
if !errorlevel! equ 0 (
    echo   √ 服务就绪！http://127.0.0.1:8000
    echo   √ API文档: http://127.0.0.1:8000/docs
    goto :done
)
set /a retries+=1
if !retries! lss 10 goto health_check

echo   [警告] 服务未在30秒内就绪，请检查 server_output.log
goto :done

:done
echo.
echo ═══════════════════════════════════════════
echo    部署完成
echo ═══════════════════════════════════════════
pause
