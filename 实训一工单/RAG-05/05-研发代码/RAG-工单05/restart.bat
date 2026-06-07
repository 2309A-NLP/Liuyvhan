@echo off
chcp 65001 > nul
echo Cleaning port 8001...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do (
  if not "%%a"=="" (
    echo Killing PID %%a
    taskkill /F /PID %%a 2>nul
  )
)
timeout /t 2 /nobreak > nul
echo Starting server...
pushd C:\Users\刘禹含\Desktop\RAG-工单04
D:\Anaconda\envs\RAG\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001
