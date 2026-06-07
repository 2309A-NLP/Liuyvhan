import subprocess, time, sys

# 1. Kill anything on port 8001
subprocess.run(
    ['powershell', '-Command',
     'Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }'],
    capture_output=True, encoding='utf-8', errors='replace',
)

# 2. List all Python processes
result = subprocess.run(
    ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV', '/NH'],
    capture_output=True, text=True, encoding='utf-8', errors='replace',
)
print(f'Python PIDs before:\n{result.stdout[:500]}')

# 3. Start uvicorn
proc = subprocess.Popen(
    ['D:\\Anaconda\\envs\\RAG\\python.exe', '-m', 'uvicorn', 'main:app', 
     '--host', '0.0.0.0', '--port', '8001', '--log-level', 'info'],
    cwd='C:\\Users\\刘禹含\\Desktop\\RAG-工单05',
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    encoding='utf-8', errors='replace',
)
print(f'Started uvicorn PID: {proc.pid}')
sys.stdout.flush()

# 4. Wait for server to start
time.sleep(20)

# 5. Check if it's listening
result2 = subprocess.run(
    ['powershell', '-Command',
     'Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | Select-Object OwningProcess, State'],
    capture_output=True, text=True, encoding='utf-8', errors='replace',
)
print(f'Port 8001 status:\n{result2.stdout[:200]}')

# 6. Check health
try:
    import urllib.request
    r = urllib.request.urlopen('http://127.0.0.1:8001/', timeout=5)
    print(f'Server response: {r.status} {r.read().decode()[:200]}')
except Exception as e:
    print(f'Health check failed: {type(e).__name__}: {e}')

# 7. Read a bit of output
time.sleep(2)
proc.poll()
if proc.returncode is not None:
    print(f'Process exited: {proc.returncode}')
    out = proc.stdout.read(2000) if proc.stdout else ''
    print(f'Output: {out}')
else:
    print('Process still running')
