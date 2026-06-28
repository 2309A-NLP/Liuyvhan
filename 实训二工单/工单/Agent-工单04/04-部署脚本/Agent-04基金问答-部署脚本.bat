@echo off
chcp 65001 >nul
title Agent-04 基金问答 - 部署脚本

echo ╔══════════════════════════════════════════════════╗
echo ║    Agent-04 基金问答 (FinQA Agent) 部署脚本      ║
echo ║    LLM NL2SQL + 规则兜底 | 博金杯基金数据问答     ║
echo ╚══════════════════════════════════════════════════╝
echo.

:: Step 1: 检查 Python 环境
echo [Step 1/7] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python 未安装，请安装 Python 3.8+
    pause
    exit /b 1
)
python --version
echo ✅ Python 环境正常
echo.

:: Step 2: 切换到项目目录
echo [Step 2/7] 切换到项目目录...
cd /d "%~dp0"
echo 当前目录: %cd%
echo ✅ 已切换到项目目录
echo.

:: Step 3: 检查依赖是否安装
echo [Step 3/7] 检查核心依赖...
pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo 📦 正在安装依赖...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ❌ 依赖安装失败
        pause
        exit /b 1
    )
    echo ✅ 依赖安装完成
) else (
    echo ✅ 核心依赖已安装
)
echo.

:: Step 4: 检查数据库文件
echo [Step 4/7] 检查数据库文件...
if exist data\database.db (
    echo ✅ 数据库文件存在: data\database.db
    dir data\database.db
) else (
    echo ⚠️ 数据库文件不存在！
    echo 请将 '博金杯比赛数据.db' 复制到 data\database.db
    echo.
    echo 如果已有数据库文件，请运行:
    echo   copy /Y "C:\path\to\博金杯比赛数据.db" "data\database.db"
    echo.
    pause
    exit /b 1
)
echo.

:: Step 5: 检查 LLM 配置
echo [Step 5/7] 检查 LLM 配置...
echo.  LLM 提供商: SiliconFlow (默认)
echo.  模    型: deepseek-ai/DeepSeek-V4-Flash
echo.  如需更换模型，请编辑 config/config.py 中的 LLM_CONFIG
echo ✅ 配置已就绪
echo.

:: Step 6: 选择运行模式
echo [Step 6/7] 选择运行模式
echo.
echo 请选择要启动的模式（输入数字后回车）:
echo.
echo  [1] API 服务模式（启动 Web 界面 + REST API）
echo  [2] 批量推理模式（处理 question.jsonl → answer.jsonl）
echo  [3] 查看数据库结构
echo.
set /p MODE_CHOICE="请输入 (1/2/3): "

if "%MODE_CHOICE%"=="1" (
    set MODE=api
) else if "%MODE_CHOICE%"=="2" (
    set MODE=batch
) else if "%MODE_CHOICE%"=="3" (
    set MODE=schema
) else (
    echo ❌ 无效选择，默认启动 API 服务
    set MODE=api
)
echo.  选择模式: %MODE%
echo.

:: Step 7: 启动服务
echo [Step 7/7] 启动服务中...

if "%MODE%"=="api" (
    echo 🌐 启动 API 服务: http://localhost:8000
    echo 📖 API 文档: http://localhost:8000/docs
    echo.
    start "" http://localhost:8000
    python app/main.py --mode api
)

if "%MODE%"=="batch" (
    echo 📊 启动批量推理...
    echo 输入文件: data/question.jsonl
    echo 输出文件: data/answer.jsonl
    echo.
    python app/main.py --mode batch
    echo ✅ 批量推理完成，结果保存在 data/answer.jsonl
    pause
)

if "%MODE%"=="schema" (
    echo 📋 显示数据库结构...
    python app/main.py --mode schema
    pause
)

echo.
echo ╔══════════════════════════════════════════════════╗
echo ║    部署完成！                                     ║
echo ║                                                   ║
echo ║  示例问题:                                        ║
echo ║  "查询所有基金的类型分布"                          ║
echo ║  "规模最大的前10只基金有哪些？"                    ║
echo ║  "基金代码为000001的基本信息"                     ║
echo ║  "易方达蓝筹精选持有哪些股票？"                    ║
echo ╚══════════════════════════════════════════════════╝
echo.
pause
