@echo off
chcp 65001 >nul
title Agent-01 记账本 — 启动脚本

echo ========================================
echo    Agent-01 记账本 — 智能记账系统
echo    FastAPI + NLP + MySQL
echo ========================================
echo.

:: 第1步：检查 Python
echo [1/7] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)
echo     Python 就绪

:: 第2步：cd 到项目目录
echo [2/7] 切换到项目目录...
cd /d "%~dp0"
echo     当前目录: %cd%

:: 第3步：检查 Conda 环境
echo [3/7] 检查 Python 版本...
python --version
echo.

:: 第4步：安装依赖
echo [4/7] 检查并安装依赖...
pip install pymysql fastapi uvicorn -q
if %errorlevel% neq 0 (
    echo [!] 依赖安装失败
    pause
    exit /b 1
)
echo     依赖就绪

:: 第5步：检查 MySQL 连接
echo [5/7] 检查 MySQL...
echo     数据库: account_book (127.0.0.1:3306)
echo     用户: root
echo     [提示] 请确保 MySQL 服务已启动且 account_book 数据库已创建
echo     确保 money_notes 表结构:
echo       id INT AUTO_INCREMENT PRIMARY KEY
echo       record_date DATE
echo       member VARCHAR(50)
echo       type VARCHAR(20)
echo       category VARCHAR(50)
echo       item VARCHAR(200)
echo       amount DECIMAL(10,2)
echo.

:: 第6步：启动 FastAPI 服务
echo [6/7] 启动 FastAPI 服务 (端口 8010)...
echo     服务地址: http://localhost:8010
echo     Web UI:   http://localhost:8010/ui/index.html
echo     API文档:  http://localhost:8010/docs
echo     健康检查: http://localhost:8010/health
echo.

start /B python main.py

:: 第7步：健康检查
echo [7/7] 等待服务启动...
set RETRIES=0
:CHECK
timeout /t 2 /nobreak >nul
curl -s http://localhost:8010/health >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo    服务启动成功！
    echo.
    echo    打开浏览器访问:
    echo    http://localhost:8010
    echo.
    echo    支持的对话示例:
    echo    - "今天女儿买了双登山鞋 499元"
    echo    - "这个月女儿花了多少钱"
    echo    - "删除女儿的买书记录"
    echo    - "把买鞋改成买书"
    echo.
    echo    家庭成员: 爸爸 / 妈妈 / 女儿
    echo    别名: 老公=爸爸, 老婆=妈妈, 孩子=女儿
    echo ========================================
    start http://localhost:8010
    pause
    exit /b 0
) else (
    set /a RETRIES+=1
    if %RETRIES% lss 10 (
        echo     正在等待... (%RETRIES%/10)
        goto CHECK
    )
    echo [!] 服务启动超时，请检查控制台输出
    pause
    exit /b 1
)
