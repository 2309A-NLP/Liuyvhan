"""
Set up Windows port forwarding: 127.0.0.1:19530 -> WSL2 VM IP:19530
This makes Milvus reachable from Windows Anaconda Python via localhost.
Run this script ANYTIME WSL is restarted (IP changes on restart).
"""
import sys, subprocess, re
sys.stdout.reconfigure(encoding='utf-8')

# Step 1: Get WSL2 VM IP from WSL
result = subprocess.run(
    ['wsl.exe', '--', 'hostname', '-I'],
    capture_output=True, text=True, timeout=10
)
wsl_ip = result.stdout.strip().split()[0] if result.stdout.strip() else None

if not wsl_ip:
    # Fallback: try ip addr
    result2 = subprocess.run(
        ['wsl.exe', '--', 'ip', 'addr', 'show', 'eth0'],
        capture_output=True, text=True, timeout=10
    )
    m = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result2.stdout)
    wsl_ip = m.group(1) if m else None

if not wsl_ip:
    print('ERROR: Cannot detect WSL2 IP address')
    sys.exit(1)

print(f'WSL2 VM IP: {wsl_ip}')

# Step 2: Delete any existing portproxy rule for 19530
subprocess.run(
    ['netsh', 'interface', 'portproxy', 'delete', 'v4tov4',
     'listenport=19530', 'listenaddress=127.0.0.1'],
    capture_output=True, text=True, timeout=10
)

# Step 3: Add new portproxy rule
result3 = subprocess.run(
    ['netsh', 'interface', 'portproxy', 'add', 'v4tov4',
     'listenport=19530', 'listenaddress=127.0.0.1',
     'connectport=19530', f'connectaddress={wsl_ip}'],
    capture_output=True, text=True, timeout=10
)

if result3.returncode == 0:
    print(f'Port forwarding added: 127.0.0.1:19530 -> {wsl_ip}:19530')
else:
    print(f'Failed to add port forwarding: {result3.stderr}')
    print('Try running this script as Administrator!')
    sys.exit(1)

# Step 4: Verify
import socket
s = socket.socket()
s.settimeout(3)
try:
    s.connect(('127.0.0.1', 19530))
    print('VERIFICATION: 127.0.0.1:19530 is reachable!')
    s.close()
except Exception as e:
    print(f'VERIFICATION FAILED: {e}')
    print('WSL2 IP might have changed. Re-run this script.')
    sys.exit(1)

# Step 5: Show all portproxy rules
result4 = subprocess.run(
    ['netsh', 'interface', 'portproxy', 'show', 'v4tov4'],
    capture_output=True, text=True, timeout=10
)
print(f'\nActive portproxy rules:\n{result4.stdout}')
