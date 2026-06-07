import subprocess, os
# Kill any process on port 8001
result = subprocess.run(
    ['powershell', '-Command',
     'Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force; Write-Output "killed $($_.OwningProcess)" }'],
    capture_output=True, text=True, encoding='utf-8', errors='replace',
)
print('STDOUT:', result.stdout)
print('STDERR:', result.stderr[:500] if result.stderr else '')
print('RC:', result.returncode)
