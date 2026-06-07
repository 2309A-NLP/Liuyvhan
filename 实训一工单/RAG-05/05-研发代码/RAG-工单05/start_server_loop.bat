@echo off
chcp 65001 > nul
title RAG Server (Port 8001) - Auto-Restart Loop
echo ============================================
echo  RAG Server 自动重启守护脚本
echo  按 Ctrl+C 可手动停止
echo ============================================

:restart
echo [%date% %time%] 清理端口 8001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do (
  if not "%%a"=="" (
    taskkill /F /PID %%a 2>nul
  )
)
timeout /t 2 /nobreak > nul

echo [%date% %time%] 启动 RAG 服务...
pushd C:\Users\刘禹含\Desktop\RAG-工单04
D:\Anaconda\envs\RAG\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001

echo [%date% %time%] 服务异常退出，10 秒后自动重启...
timeout /t 10 /nobreak > nul
goto restart
