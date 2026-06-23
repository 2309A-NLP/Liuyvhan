@echo off
chcp 65001 >nul
title Linly-Talker 数字人系统部署脚本

echo ========================================
echo   Linly-Talker 数字人智能对话系统
echo   部署启动脚本
echo ========================================
echo.

REM ===== 第1步：检查CUDA可用性 =====
echo [1/7] 检查CUDA环境...
nvcc --version >nul 2>&1
if %errorlevel% equ 0 (
    echo   CUDA 已安装
    nvcc --version | findstr "release"
) else (
    echo   [警告] CUDA未检测到，将使用CPU模式（性能受限）
)
echo.

REM ===== 第2步：进入项目目录 =====
echo [2/7] 进入项目目录...
cd /d "C:\Users\刘禹含\Desktop\Linly-Talker\Linly-Talker"
if %errorlevel% neq 0 (
    echo   [错误] 项目目录不存在！
    pause
    exit /b 1
)
echo   当前目录: %cd%
echo.

REM ===== 第3步：检查Python环境 =====
echo [3/7] 检查Python环境...
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('python --version') do echo   Python: %%i
) else (
    echo   [错误] 未找到Python，请安装Python 3.10+
    pause
    exit /b 1
)

REM 检查PyTorch CUDA
python -c "import torch; print(f'  PyTorch: {torch.__version__}'); print(f'  CUDA可用: {torch.cuda.is_available()}'); print(f'  GPU数量: {torch.cuda.device_count()}')" 2>nul
echo.

REM ===== 第4步：检查依赖 =====
echo [4/7] 检查核心依赖...
python -c "import gradio; print(f'  Gradio: {gradio.__version__}')" 2>nul || echo   [警告] gradio 未安装
python -c "import transformers; print(f'  transformers: {transformers.__version__}')" 2>nul || echo   [警告] transformers 未安装
python -c "import edge_tts; print(f'  edge-tts: 已安装')" 2>nul || echo   [警告] edge-tts 未安装
python -c "import librosa; print(f'  librosa: {librosa.__version__}')" 2>nul || echo   [警告] librosa 未安装
echo.

REM ===== 第5步：检查模型文件 =====
echo [5/7] 检查模型文件...
if exist "checkpoints\*" (
    echo   模型文件: 已找到
) else (
    echo   [提示] 模型文件未检测到
    echo   首次运行会自动下载或使用API模式
)
echo.

REM ===== 第6步：选择启动方式 =====
echo [6/7] 选择启动模式
echo.
echo   启动方式：
echo   1 - WebUI 完整界面（推荐）
echo   2 - 基础对话 (app.py)
echo   3 - 图片数字人对话 (app_img.py)
echo   4 - 多轮对话 (app_multi.py)
echo   5 - MuseTalk 实时对话 (app_musetalk.py)
echo   6 - 语音克隆对话 (app_talk.py)
echo   7 - API 服务 (先安装依赖: pip install -r api/requirements.txt)
echo   8 - 退出
echo.
set /p MODE="请选择启动方式 (1-8): "

if "%MODE%"=="1" goto webui
if "%MODE%"=="2" goto app
if "%MODE%"=="3" goto app_img
if "%MODE%"=="4" goto app_multi
if "%MODE%"=="5" goto app_musetalk
if "%MODE%"=="6" goto app_talk
if "%MODE%"=="7" goto api
if "%MODE%"=="8" goto end
echo   无效选择，使用默认(1)
goto webui

:webui
echo   启动 WebUI 完整界面...
echo   访问地址: http://localhost:6006
start http://localhost:6006
python webui.py
goto end

:app
echo   启动基础对话模式...
echo   访问地址: http://localhost:6006
start http://localhost:6006
python app.py
goto end

:app_img
echo   启动图片数字人对话...
echo   访问地址: http://localhost:6006
start http://localhost:6006
python app_img.py
goto end

:app_multi
echo   启动多轮对话模式...
echo   访问地址: http://localhost:6006
start http://localhost:6006
python app_multi.py
goto end

:app_musetalk
echo   启动 MuseTalk 实时对话...
echo   访问地址: http://localhost:6006
start http://localhost:6006
python app_musetalk.py
goto end

:app_talk
echo   启动语音克隆对话...
echo   访问地址: http://localhost:6006
start http://localhost:6006
python app_talk.py
goto end

:api
echo   启动 API 服务...
echo.
echo   TTS API:  http://localhost:8001  (pip install -r api/requirements.txt)
echo   LLM API:  http://localhost:8002
echo   Talker:   http://localhost:8003
echo.
start http://localhost:8001/docs
start http://localhost:8002/docs
start http://localhost:8003/docs
start cmd /k "python api/tts_api.py"
start cmd /k "python api/llm_api.py"
start cmd /k "python api/talker_api.py"
echo   API 服务已启动，请访问各端口
goto end

:end
echo.
echo ========================================
echo   感谢使用 Linly-Talker!
echo   项目地址: https://github.com/Kedreamix/Linly-Talker
echo ========================================
pause
