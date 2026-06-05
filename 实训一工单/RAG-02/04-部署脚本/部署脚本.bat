@echo off
chcp 65001 >nul
title RAG 招股说明书问答系统 — 部署脚本
color 0B

echo ====================================================
echo    RAG 招股说明书问答系统 — 一键部署脚本
echo ====================================================
echo.

:: ===== Step 1: 检查并启动 Docker 服务 =====
echo [1/7] 检查 Docker 容器状态...
docker ps --format "{{.Names}}" | findstr "milvus-standalone" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  ! Milvus 未在运行，正在启动...
    docker start milvus-etcd milvus-minio milvus-standalone 2>nul
    docker start rag-redis 2>nul
    timeout /t 5 /nobreak >nul
) else (
    echo  ✓ Milvus 和 Redis 容器运行中
)
echo.

:: ===== Step 2: 检查项目路径 =====
echo [2/7] 设置项目路径...
set PROJECT_DIR=D:\工单完整\RAG\RAG-工单02
if not exist "%PROJECT_DIR%" (
    echo  ✗ 项目目录不存在: %PROJECT_DIR%
    pause
    exit /b 1
)
cd /d "%PROJECT_DIR%"
echo  ✓ 项目目录: %CD%
echo.

:: ===== Step 3: 检查 Python 环境 =====
echo [3/7] 检查 Python 环境...
set PYTHON=D:\Anaconda\envs\RAG\python.exe
if not exist "%PYTHON%" (
    echo  ✗ Python 环境不存在: %PYTHON%
    pause
    exit /b 1
)
"%PYTHON%" --version
echo  ✓ Python 环境正常
echo.

:: ===== Step 4: 检查配置文件 =====
echo [4/7] 检查配置文件...
if not exist ".env" (
    echo  ✗ .env 配置文件不存在
    pause
    exit /b 1
)
echo  ✓ .env 配置已加载
echo.

:: ===== Step 5: 检查模型缓存 =====
echo [5/7] 检查 AI 模型缓存...
set CACHE_DIR=%USERPROFILE%\.cache\huggingface\hub
if exist "%CACHE_DIR%\models--BAAI--bge-reranker-v2-m3" (
    echo  ✓ 重排模型已缓存
) else (
    echo  - BGE reranker 模型未缓存，启动时会自动下载
)
echo.

:: ===== Step 6: 启动 API 服务 =====
echo [6/7] 启动 RAG API 服务...
echo  端口: 8000
echo  日志: server.log
echo.
start /B "" "%PYTHON%" -m uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1

:: 等待服务就绪
echo  等待服务就绪...
:WAIT_LOOP
timeout /t 3 /nobreak >nul
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1"
if %ERRORLEVEL% neq 0 (
    set /a COUNT=COUNT+1
    if !COUNT! lss 20 goto WAIT_LOOP
    echo  ✗ 服务启动超时，请检查 server.log
    pause
    exit /b 1
)
echo  ✓ API 服务启动成功！http://localhost:8000
echo.

:: ===== Step 7: 验证 =====
echo [7/7] 验证服务状态...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/status' -UseBasicParsing; Write-Host $r.Content } catch { Write-Host 'Status check failed' }"
echo.
echo ====================================================
echo  部署完成！
echo.
echo  API 文档:
echo    Swagger UI: http://localhost:8000/docs
echo    ReDoc:      http://localhost:8000/redoc
echo.
echo  常用命令:
echo    查看日志:  type server.log
echo    停止服务:  taskkill /f /fi "WINDOWTITLE eq RAG*" 2^>nul
echo ====================================================
echo.
pause
