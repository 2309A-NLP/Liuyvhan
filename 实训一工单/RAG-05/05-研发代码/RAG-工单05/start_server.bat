@echo off
pushd "C:\Users\刘禹含\Desktop\RAG-工单05"
chcp 65001 > NUL
D:\Anaconda\envs\RAG\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 --log-level debug > server_output.log 2>&1
