@echo off
chcp 65001 >nul
pushd C:\Users\刘禹含\Desktop\RAG-工单04
start /B D:\Anaconda\envs\RAG\python.exe -u -m uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1
