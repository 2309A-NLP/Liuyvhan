import subprocess

# Kill EVERYTHING on port 8001 aggressively
for _ in range(3):
    result = subprocess.run(
        ['powershell', '-Command',
         'Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | ForEach-Object { Write-Output ("Killing PID " + $_.OwningProcess); Stop-Process -Id $_.OwningProcess -Force }'],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
    )
    print(result.stdout)
    if result.stdout.strip():
        import time
        time.sleep(1)

# Verify port is clear
result = subprocess.run(
    ['powershell', '-Command',
     'Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | Select-Object OwningProcess, State'],
    capture_output=True, text=True, encoding='utf-8', errors='replace',
)
print(f'After cleanup:\n{result.stdout[:200]}')
print('DONE' if not result.stdout.strip() else 'STILL IN USE!')
