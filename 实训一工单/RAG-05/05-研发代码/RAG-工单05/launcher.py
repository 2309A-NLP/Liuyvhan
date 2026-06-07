#!/usr/bin/env python3
"""Kill Windows Python on port 8001 then launch server."""
import subprocess, time

# Kill
subprocess.run(['taskkill.exe', '/F', '/IM', 'python.exe'], 
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
print("Killed old python processes")

# Launch
subprocess.Popen(
    ['cmd.exe', '/c', r'C:\Users\刘禹含\Desktop\RAG-工单05\start_server.bat'],
    cwd='/mnt/c/'
)
print("Launching server...")
