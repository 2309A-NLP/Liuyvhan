import socket, sys
s = socket.socket()
try:
    s.connect(('127.0.0.1', 8001))
    print('CONNECTED')
    s.close()
except Exception as e:
    print(f'FAILED: {e}')
