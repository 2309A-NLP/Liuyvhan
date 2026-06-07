import subprocess, time

# Read uvicorn output
result = subprocess.run(
    ['powershell', '-Command', 
     'Get-Process -Id 31176 -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime, @{N="CPUs";E={$_.CPU}} | Format-List'],
    capture_output=True, text=True, encoding='utf-8', errors='replace',
)
print('Process info:')
print(result.stdout[:500])

# Check port again after 40s total
time.sleep(25)
result2 = subprocess.run(
    ['powershell', '-Command',
     'Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | Select-Object OwningProcess, State, LocalAddress'],
    capture_output=True, text=True, encoding='utf-8', errors='replace',
)
print(f'Port 8001 after 45s:\n{result2.stdout[:200]}')

# Try health
try:
    import urllib.request
    r = urllib.request.urlopen('http://127.0.0.1:8001/', timeout=5)
    print(f'Server OK: {r.status}')
except Exception as e:
    print(f'Server NOT ready: {type(e).__name__}: {e}')

# Check if PID 31176 still exists
result3 = subprocess.run(
    ['tasklist', '/FI', 'PID eq 31176', '/FO', 'CSV', '/NH'],
    capture_output=True, text=True, encoding='utf-8', errors='replace',
)
print(f'PID 31176 status: {result3.stdout[:100] if result3.stdout else "not found"}')
