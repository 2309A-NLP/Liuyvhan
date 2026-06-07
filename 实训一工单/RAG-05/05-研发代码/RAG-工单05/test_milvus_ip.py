"""Test Milvus connectivity using WSL2 VM IP"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import socket

# WSL2 VM IP (from ip addr show eth0)
wsl2_ip = '172.18.224.39'

def test(host, port, label):
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

# Test Milvus via WSL2 VM direct IP
test(wsl2_ip, 19530, f'Windows->{wsl2_ip}:19530 (Milvus via WSL IP)')
# Test Redis via WSL2 VM direct IP
test(wsl2_ip, 6379, f'Windows->{wsl2_ip}:6379 (Redis via WSL IP)')
# Compare: 127.0.0.1 for Redis (should work via forwarding)
test('127.0.0.1', 6379, 'Windows->127.0.0.1:6379 (Redis fwd)')
test('127.0.0.1', 19530, 'Windows->127.0.0.1:19530 (Milvus fwd)')
