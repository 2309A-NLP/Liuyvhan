@echo off
pushd C:\Users\刘禹含\Desktop\RAG-工单04
chcp 65001 > nul
D:\Anaconda\envs\RAG\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001
