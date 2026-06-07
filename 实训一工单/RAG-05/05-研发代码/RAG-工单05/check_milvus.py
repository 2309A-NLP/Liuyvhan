import urllib.request, json
try:
    r = urllib.request.urlopen('http://127.0.0.1:19530/', timeout=5)
    print(f'Milvus HTTP: {r.status} {r.read().decode()[:100]}')
except Exception as e:
    print(f'Milvus HTTP failed: {type(e).__name__}: {e}')

try:
    r = urllib.request.urlopen('http://host.docker.internal:19530/', timeout=5)
    print(f'Milvus via host.docker.internal: {r.status} {r.read().decode()[:100]}')
except Exception as e:
    print(f'Milvus via host.docker.internal failed: {type(e).__name__}: {e}')

# Try WSL2 gateway IP
try:
    r = urllib.request.urlopen('http://172.18.224.1:19530/', timeout=5)
    print(f'Milvus via 172.18.224.1: {r.status} {r.read().decode()[:100]}')
except Exception as e:
    print(f'Milvus via 172.18.224.1 failed: {type(e).__name__}: {e}')
