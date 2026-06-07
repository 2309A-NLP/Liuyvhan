import sys, urllib.request, json
sys.stdout.reconfigure(encoding='utf-8')

try:
    r = urllib.request.urlopen('http://127.0.0.1:8001/', timeout=5)
    body = r.read().decode()
    print(f'ROOT: status={r.status}', flush=True)
    print(f'Body: {body[:150]}', flush=True)
except Exception as e:
    print(f'FAILED: {e}', flush=True)
