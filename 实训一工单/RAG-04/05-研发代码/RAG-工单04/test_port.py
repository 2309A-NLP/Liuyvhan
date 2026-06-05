import socket
s = socket.socket()
s.bind(('0.0.0.0', 8001))
s.close()
print("8001 ok")
