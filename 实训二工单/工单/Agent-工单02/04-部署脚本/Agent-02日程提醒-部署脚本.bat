@echo off
chcp 65001 >nul
title 日程管家 - 部署启动脚本

echo ============================================================
echo  日程管家 - Agent-02 日程提醒 部署脚本
echo  端口：8012 | 数据库：MySQL schedule_reminder
echo ============================================================
echo.

:: ===== Step 1: 检查 Python 环境 =====
echo [1/7] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python，请安装 Python 3.10+
    pause
    exit /b 1
)
python --version
echo ✅ Python 环境正常
echo.

:: ===== Step 2: 进入项目目录 =====
echo [2/7] 进入项目目录...
cd /d "%~dp0"
echo ✅ 当前目录: %cd%
echo.

:: ===== Step 3: 安装依赖 =====
echo [3/7] 检查并安装依赖...
pip install -r backend\requirements.txt -q 2>&1 | findstr /V "already satisfied"
if %errorlevel% neq 0 (
    echo ⚠️ 部分依赖可能需要手动安装
)
echo ✅ 依赖检查完成
echo.

:: ===== Step 4: 检查配置 =====
echo [4/7] 检查配置文件...
if exist .env (
    echo ✅ 配置文件 .env 已存在
    echo ── 关键配置 ──
    findstr "APP_PORT" .env
    findstr "MYSQL_" .env
    findstr "LLM_MODEL" .env
    findstr "LLM_API_BASE" .env
    echo ────────────
) else (
    echo ⚠️ .env 文件不存在，将使用默认配置
    echo   端口: 8012, 数据库: mysql://root@127.0.0.1:3306/schedule_reminder
    echo   如需修改配置请创建 .env 文件
)
echo.

:: ===== Step 5: 检查 MySQL 数据库 =====
echo [5/7] 检查 MySQL 数据库连接...
python -c "
import mysql.connector
try:
    conn = mysql.connector.connect(
        host='127.0.0.1', port=3306,
        user='root', password='root',
        charset='utf8mb4'
    )
    print('✅ MySQL 连接成功')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM `schedule_reminder`.`schedules`')
    count = cursor.fetchone()[0]
    print(f'📊 当前日程数: {count}')
    cursor.close()
    conn.close()
except Exception as e:
    print(f'⚠️ MySQL 连接失败: {e}')
    print('   请确保 MySQL 服务已启动（localhost:3306）')
" 2>&1
echo.

:: ===== Step 6: 启动服务 =====
echo [6/7] 启动日程管家服务...
echo   地址: http://localhost:8012
echo   接口: POST /chat
echo   日程: GET /list
echo   提醒: GET /due
echo   界面: http://localhost:8012
echo.

start /B python backend\main.py > backend\server.log 2>&1

:: ===== Step 7: 等待服务启动 =====
echo [7/7] 等待服务启动...
timeout /t 3 /nobreak >nul

:: 检查是否启动成功
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if %errorlevel% equ 0 (
    echo ✅ 日程管家服务已启动！
    echo.
    echo ============================================================
    echo  打开浏览器访问: http://localhost:8012
    echo  示例对话：
    echo    - 「明天下午5点提醒我开会」
    echo    - 「看看我今天有什么安排」
    echo    - 「每天早上8点提醒我起床」
    echo    - 「删除日程1」
    echo    - 「修改日程1的时间到明天下午4点」
    echo ============================================================
    start http://localhost:8012
) else (
    echo ❌ 服务启动失败，请查看 backend\server.log
)

echo.
pause
