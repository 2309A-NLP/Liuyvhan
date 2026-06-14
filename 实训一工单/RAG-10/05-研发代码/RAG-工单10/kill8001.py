"""Kill any process on port 8001 - run from Windows Anaconda"""
import subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')

r = subprocess.run(
    ['powershell', '-Command',
     'Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | '
     'Select-Object -ExpandProperty OwningProcess | '
     'ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; Write-Output "Killed PID $_" }'],
    capture_output=True, text=True, timeout=15
)
output = r.stdout.strip() or 'No process on port 8001'
print(output)
