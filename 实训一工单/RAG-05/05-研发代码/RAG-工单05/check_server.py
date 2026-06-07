import urllib.request, json
try:
    r = urllib.request.urlopen('http://127.0.0.1:8001/', timeout=10)
    print('ROOT:', r.status, r.read().decode())
    r2 = urllib.request.urlopen('http://127.0.0.1:8001/api/v1/health', timeout=10)
    print('HEALTH:', r2.status, r2.read().decode())
except Exception as e:
    print('ERR:', type(e).__name__, e)
