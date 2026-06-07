"""Check if port 8001 is listening from Windows side"""
import socket, sys
sys.stdout.reconfigure(encoding='utf-8')

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(3)
try:
    s.connect(('127.0.0.1', 8001))
    print('PORT 8001: LISTENING', flush=True)
    s.close()
except ConnectionRefusedError:
    print('PORT 8001: REFUSED (not ready yet)', flush=True)
except Exception as e:
    print(f'PORT 8001: ERROR - {e}', flush=True)

import subprocess
r = subprocess.run(
    ['powershell', '-Command',
     'Get-Process -Id 23434 -ErrorAction SilentlyContinue | Select-Object ProcessName,CPU,StartTime,Responding'],
    capture_output=True, text=True, timeout=10
)
if r.stdout.strip():
    print(f'Process 23434:\n{r.stdout.strip()}', flush=True)
else:
    print('Process 23434 no longer exists', flush=True)
