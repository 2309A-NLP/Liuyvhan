"""Check if WSL2 localhost forwarding works for other ports from Windows side"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import socket

def test_port(host, port, label):
    s = socket.socket()
    s.settimeout(3)
    try:
        s.connect((host, port))
        print(f'{label}: CONNECTED')
        s.close()
        return True
    except Exception as e:
        print(f'{label}: FAILED - {e}')
        return False

# Test Redis (should work - it's on 6379)
test_port('127.0.0.1', 6379, 'Windows->127.0.0.1:6379 (Redis)')

# Test Milvus
test_port('127.0.0.1', 19530, 'Windows->127.0.0.1:19530 (Milvus)')

# Test the WSL2 gateway
test_port('172.18.224.1', 6379, 'Windows->172.18.224.1:6379 (Redis via GW)')
test_port('172.18.224.1', 19530, 'Windows->172.18.224.1:19530 (Milvus via GW)')

# Also check if there's a .wslconfig issue
import subprocess
r = subprocess.run(['wsl', '--version'], capture_output=True, text=True)
print(f'\nWSL version:\n{r.stdout.strip()}')
