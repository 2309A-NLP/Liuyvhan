@echo off
chcp 65001 >nul
title RAG-工单04 一键部署脚本
setlocal enabledelayedexpansion

echo ============================================
echo   RAG-工单04 一键部署脚本
echo   多模态语义检索系统
echo ============================================
echo.

REM ---- Step 1: 检查 Docker 容器 ----
echo [Step 1/7] 检查 Docker 容器状态...
docker ps --format "{{.Names}}" 2>nul | findstr /I "rag-redis" >nul
if %errorlevel%==0 ( echo   rag-redis ... 运行中 ) else ( echo   WARNING: rag-redis 未运行，请启动 Docker 容器 )

docker ps --format "{{.Names}}" 2>nul | findstr /I "milvus" >nul
if %errorlevel%==0 ( echo   Milvus 容器 ... 运行中 ) else ( echo   WARNING: Milvus 未运行，请启动 Docker 容器 )
echo.

REM ---- Step 2: 切换到项目目录 ----
echo [Step 2/7] 切换到项目目录...
cd /d "D:\工单完整\RAG\RAG-工单04"
echo   当前目录: %cd%
echo.

REM ---- Step 3: 检查 Python 环境 ----
echo [Step 3/7] 检查 Python 环境...
set PYTHON=D:\Anaconda\envs\RAG\python.exe
if not exist "%PYTHON%" (
    echo   ERROR: 未找到 Conda 环境: %PYTHON%
    echo   请修改 PYTHON 路径指向您的 RAG 环境
    pause
    exit /b 1
)
echo   Python: %PYTHON%
%PYTHON% --version
echo.

REM ---- Step 4: 检查 .env 配置文件 ----
echo [Step 4/7] 检查 .env 配置文件...
if not exist ".env" (
    echo   ERROR: 未找到 .env 文件！
    pause
    exit /b 1
)
echo   .env 文件存在 ✓
REM 确保离线模式开启
powershell -Command "$c = Get-Content '.env' -Raw; if($c -notmatch 'HF_HUB_OFFLINE') { Add-Content '.env' \"`nHF_HUB_OFFLINE=1`nTRANSFORMERS_OFFLINE=1\" }"
echo   离线模式已配置 ✓
echo.

REM ---- Step 5: 检查模型缓存 ----
echo [Step 5/7] 检查模型缓存...
set RERANKER_PATH=C:\Users\刘禹含\.cache\huggingface\hub\models--BAAI--bge-reranker-v2-m3
if exist "%RERANKER_PATH%" ( echo   BAAI/bge-reranker-v2-m3 ... 已缓存 ✓ ) else ( echo   WARNING: Reranker 模型未缓存，首次运行需联网下载 )

set CLIP_PATH=C:\models\clip-vit-base-patch32
if exist "%CLIP_PATH%" ( echo   openai/clip-vit-base-patch32 ... 本地已就绪 ✓ ) else ( echo   WARNING: CLIP 模型未就绪，检查 C:\models\clip-vit-base-patch32 )

set EMBEDDING_PATH=D:\m3e\人工智能NLP专高２新增附件 m3e-base\m3e-base
if exist "%EMBEDDING_PATH%" ( echo   m3e-base ... 本地已就绪 ✓ ) else ( echo   WARNING: m3e-base 未找到，将使用 sentence-transformers 在线加载 )
echo.

REM ---- Step 6: 启动 uvicorn 服务 ----
echo [Step 6/7] 启动 RAG API 服务 (后台)...
set LOGFILE=server_%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%.log

start "RAG-Ticket04" /B %PYTHON% -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > "%LOGFILE%" 2>&1
echo   服务已启动，PID 见任务管理器
echo   日志文件: %LOGFILE%
echo.

REM ---- Step 7: 验证服务 ----
echo [Step 7/7] 验证服务是否启动...
set RETRIES=0
:CHECK
timeout /t 3 /nobreak >nul
curl -s http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel%==0 (
    echo   服务启动成功！http://127.0.0.1:8000
    echo   接口文档: http://127.0.0.1:8000/docs
    echo.
    echo ============================================
    echo   部署完成
    echo   RAG-工单04 已就绪！
    echo   注意: 首次请求会自动构建 BM25 索引和 Milvus
    echo ============================================
    goto :END
)
set /a RETRIES+=1
if %RETRIES% LSS 15 (
    echo   等待服务启动... (%RETRIES%/15)
    goto :CHECK
)
echo   WARNING: 服务未能在45秒内响应，请检查日志文件 %LOGFILE%
echo   可以手动运行: %PYTHON% -m uvicorn main:app --host 0.0.0.0 --port 8000

:END
echo.
echo 按任意键退出...
pause >nul
