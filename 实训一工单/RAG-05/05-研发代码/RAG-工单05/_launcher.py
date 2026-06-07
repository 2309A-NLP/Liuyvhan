#!/usr/bin/env python3
"""Launch RAG-工单05 server on Windows Anaconda Python from WSL."""
import subprocess, os

bat_content = r"""@echo off
chcp 65001 >nul
pushd C:\Users\刘禹含\Desktop\RAG-工单05
echo [%date% %time%] Starting uvicorn... >> server.log
D:\Anaconda\envs\RAG\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001 --log-level info >> server.log 2>&1
"""

bat_path = r"C:\Users\刘禹含\Desktop\RAG-工单05\start_server.bat"
with open(bat_path, 'w', encoding='utf-8') as f:
    f.write(bat_content)

# Launch via cmd.exe with proper directory
result = subprocess.run(
    ['cmd.exe', '/c', 'start', '', bat_path],
    cwd='C:\\',
    capture_output=True,
    text=True,
    timeout=5
)
print(f"Launched. stdout={result.stdout[:200]}, stderr={result.stderr[:200]}, rc={result.returncode}")
