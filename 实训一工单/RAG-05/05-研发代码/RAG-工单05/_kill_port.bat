
@echo off
chcp 65001 >nul
for /f "tokens=5" %a in ('netstat -ano ^| findstr ":8001"') do taskkill /F /PID %a 2>nul
echo done
