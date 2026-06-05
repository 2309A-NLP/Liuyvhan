@echo off
chcp 65001 >nul
title RAG-工单01 一键部署脚本

echo ========================================
echo   RAG-工单01 招股书问答系统 - 部署脚本
echo ========================================
echo.

:: ======== Step 1: 检查 Docker ========
echo [1/7] 检查 Docker 容器状态...
docker ps --format "{{.Names}}" 2>nul | findstr "rag-redis" >nul
if %errorlevel% neq 0 (
    echo [!] Redis 容器未运行，请先启动 Docker 容器：
    echo     docker start rag-redis milvus-etcd milvus-minio milvus-standalone
    echo.
    set /p START_DOCKER="是否自动启动 Docker 容器? (y/n): "
    if /i "!START_DOCKER!"=="y" (
        docker start rag-redis milvus-etcd milvus-minio milvus-standalone
        if %errorlevel% neq 0 (
            echo [x] Docker 启动失败，请手动检查。
            pause
            exit /b 1
        )
        echo [v] Docker 容器已启动
    ) else (
        pause
        exit /b 1
    )
) else (
    echo [v] Docker 容器运行正常
)

:: ======== Step 2: 设置项目路径 ========
echo.
echo [2/7] 设置项目路径...
set PROJECT_DIR=D:\工单完整\RAG\RAG-工单01
if not exist "%PROJECT_DIR%" (
    echo [x] 项目目录不存在: %PROJECT_DIR%
    pause
    exit /b 1
)
cd /d "%PROJECT_DIR%"
echo [v] 项目路径: %PROJECT_DIR%

:: ======== Step 3: 检查 Python 环境 ========
echo.
echo [3/7] 检查 Python 环境...
set PYTHON_EXE=D:\Anaconda\envs\RAG\python.exe
if not exist "%PYTHON_EXE%" (
    echo [x] Conda 环境未找到: %PYTHON_EXE%
    echo     请确认 D:\Anaconda\envs\RAG\ 存在
    pause
    exit /b 1
)
echo [v] Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version

:: ======== Step 4: 检查配置文件 ========
echo.
echo [4/7] 检查配置文件...
if not exist ".env" (
    echo [x] .env 文件缺失
    if exist ".env.example" (
        copy .env.example .env
        echo [i] 已从 .env.example 生成 .env，请编辑配置
    ) else (
        pause
        exit /b 1
    )
)
echo [v] .env 配置已存在

:: ======== Step 5: 检查模型缓存 ========
echo.
echo [5/7] 检查本地模型缓存...
set HF_CACHE=%USERPROFILE%\.cache\huggingface\hub
if exist "%HF_CACHE%\models--BAAI--bge-reranker-v2-m3" (
    echo [v] Reranker 模型已缓存 (BAAI/bge-reranker-v2-m3)
) else (
    echo [i] Reranker 模型未缓存，将使用在线加载
    echo     注意：离线环境下需要在 .env 设置 ENABLE_RERANKER=false
)

if exist "D:\m3e\人工智能NLP专高２新增附件 m3e-base\m3e-base" (
    echo [v] m3e-base 嵌入模型已就绪
) else (
    echo [i] 将使用 sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
)

:: ======== Step 6: 启动 API 服务 ========
echo.
echo [6/7] 启动 RAG API 服务...
echo 端口: 8000
echo 启动中... (首次启动约需 10-15秒加载模型)
echo.

:: 在 .env 中设置离线模式，避免 HuggingFace 连接超时
powershell -Command "$c = Get-Content '.env' -Raw; if($c -notmatch 'HF_HUB_OFFLINE') { Add-Content '.env' \"`nHF_HUB_OFFLINE=1`nTRANSFORMERS_OFFLINE=1\" }" >nul 2>&1

start /B "" "%PYTHON_EXE%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info > rag_server.log 2>&1
if %errorlevel% neq 0 (
    echo [x] 服务启动失败，请查看 rag_server.log
    pause
    exit /b 1
)

:: ======== Step 7: 验证服务状态 ========
echo.
echo [7/7] 验证服务状态...
echo 等待服务就绪...

:wait_loop
timeout /t 3 /nobreak >nul
powershell -Command "try{$r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0}}catch{}; exit 1" >nul 2>&1
if %errorlevel% neq 0 (
    set /a attempts+=1
    if !attempts! geq 10 (
        echo [x] 服务启动超时，请查看 rag_server.log
        pause
        exit /b 1
    )
    goto wait_loop
)

echo.
echo ========================================
echo   [v] 部署完成!
echo ========================================
echo.
echo   服务地址: http://localhost:8000
echo   API 文档: http://localhost:8000/docs
echo   健康检查: http://localhost:8000/api/v1/health
echo.
echo   日志文件: %PROJECT_DIR%\rag_server.log
echo.
echo   如需停止服务，关闭此窗口即可。
echo ========================================

:: 打开浏览器
start http://localhost:8000/docs

pause
