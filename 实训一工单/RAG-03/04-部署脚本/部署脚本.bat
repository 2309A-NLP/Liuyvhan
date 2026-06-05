@echo off
chcp 65001 > nul
title RAG-工单03 一键部署脚本
echo ============================================
echo   RAG-工单03 部署启动脚本
echo   RAG Prospectus QA API (双文档自动分档)
echo ============================================
echo.

:: Step 1: 检查 Docker 服务 (Milvus + Redis)
echo [Step 1/7] 检查 Docker 容器状态...
docker ps --format "{{.Names}}" 2>nul | findstr "rag-redis" >nul
if %errorlevel% neq 0 (
    echo [警告] rag-redis 容器未运行！请先启动 Docker。
    echo 运行: docker compose up -d
    pause
    exit /b 1
)
echo   rag-redis: 运行中

docker ps --format "{{.Names}}" 2>nul | findstr "milvus-standalone" >nul
if %errorlevel% neq 0 (
    echo [警告] milvus-standalone 未运行！
    pause
    exit /b 1
)
echo   milvus-standalone: 运行中
echo.

:: Step 2: 设置项目路径
echo [Step 2/7] 设置项目路径...
set PROJECT_DIR=D:\工单完整\RAG\RAG-工单03
set CONDA_PYTHON=D:\Anaconda\envs\RAG\python.exe
if not exist "%PROJECT_DIR%" (
    echo [错误] 项目目录不存在: %PROJECT_DIR%
    pause
    exit /b 1
)
cd /d "%PROJECT_DIR%"
echo   项目目录: %PROJECT_DIR%
echo.

:: Step 3: 检查 Python 环境
echo [Step 3/7] 检查 Python 环境...
if not exist "%CONDA_PYTHON%" (
    echo [错误] Conda 环境未找到: %CONDA_PYTHON%
    echo 请先创建 conda 环境: conda create -n RAG python=3.12
    pause
    exit /b 1
)
echo   Python: %CONDA_PYTHON%
echo.

:: Step 4: 检查依赖
echo [Step 4/7] 检查 Python 依赖...
if not exist "requirements.txt" (
    echo [错误] requirements.txt 不存在！
    pause
    exit /b 1
)
"%CONDA_PYTHON%" -c "import fastapi" 2>nul
if %errorlevel% neq 0 (
    echo [信息] 安装依赖中...
    "%CONDA_PYTHON%" -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
)
echo   依赖已就绪
echo.

:: Step 5: 检查模型缓存 (m3e-base + reranker)
echo [Step 5/7] 检查嵌入模型...
set HF_CACHE=%USERPROFILE%\.cache\huggingface\hub
if exist "%PROJECT_DIR%\..\..\m3e\人工智能NLP专高２新增附件 m3e-base\m3e-base" (
    echo   本地 m3e-base 模型: 已找到
) else (
    echo   [信息] 使用 paraphrase-MiniLM 云端模型 (需联网首加载)
)

echo   检查 reranker 缓存...
if exist "%HF_CACHE%\models--BAAI--bge-reranker-v2-m3" (
    echo   bge-reranker-v2-m3: 已缓存
) else (
    echo   [信息] reranker 需要首次联网加载
)
echo.

:: Step 6: 启动 API 服务
echo [Step 6/7] 启动 RAG API 服务...
echo   端口: 8000
echo   日志: rag_server.log
echo.

:: 修改 .env 禁用 reranker (避免 HuggingFace 连接阻塞)
echo [信息] 确保 offline 模式...
powershell -Command "$c = Get-Content '.env' -Raw; if ($c -notmatch 'HF_HUB_OFFLINE') { $c += \"`nHF_HUB_OFFLINE=1`nTRANSFORMERS_OFFLINE=1\"; [System.IO.File]::WriteAllText('.env', $c, [System.Text.Encoding]::UTF8) }"

:: 在后台启动服务器
start /B "" "%CONDA_PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 > rag_server.log 2>&1
echo   服务器启动中...
echo.

:: Step 7: 验证服务状态
echo [Step 7/7] 验证服务状态...
timeout /t 5 /nobreak >nul

:: 通过 PowerShell 请求健康检查
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/health' -UseBasicParsing -TimeoutSec 5; if ($r.StatusCode -eq 200) { Write-Host '  服务运行正常!' -ForegroundColor Green; exit 0 } } catch {}; Write-Host '  服务启动失败，请检查 rag_server.log' -ForegroundColor Red; exit 1"

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   部署成功！
    echo   接口地址: http://localhost:8000
    echo   API 文档: http://localhost:8000/docs
    echo.
    echo   测试命令:
    echo   curl http://127.0.0.1:8000/api/v1/health
    echo.
    echo   自动分档示例:
    echo   POST /api/v1/chat/rag {^"question^":^"武汉兴图新科注册资本是多少？^"}
    echo   POST /api/v1/chat/rag {^"question^":^"力源信息发行股数？^"}
    echo ============================================
) else (
    echo.
    echo [错误] 服务启动失败，查看 rag_server.log
    type rag_server.log
)

pause
