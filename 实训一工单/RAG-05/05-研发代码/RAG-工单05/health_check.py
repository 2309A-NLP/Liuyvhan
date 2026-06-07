"""Health check the RAG server"""
import sys, urllib.request, json
sys.stdout.reconfigure(encoding='utf-8')

urls = [
    ('Root', 'http://127.0.0.1:8001/'),
    ('Health', 'http://127.0.0.1:8001/health'),
]

for name, url in urls:
    try:
        r = urllib.request.urlopen(url, timeout=5)
        body = r.read().decode('utf-8')[:150]
        print(f'{name}: Status={r.status}, Body={body}', flush=True)
    except Exception as e:
        print(f'{name}: FAILED - {e}', flush=True)
