"""Test RAG endpoint"""
import sys, urllib.request, json
sys.stdout.reconfigure(encoding='utf-8')

payload = json.dumps({"question": "发了几股", "top_k": 3}).encode('utf-8')
req = urllib.request.Request(
    'http://127.0.0.1:8001/api/v1/chat/rag',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

print('Sending RAG query: "发了几股"', flush=True)
try:
    r = urllib.request.urlopen(req, timeout=120)
    body = json.loads(r.read().decode('utf-8'))
    print(f'Status={r.status}', flush=True)
    print(f'Answer: {body.get("answer", "N/A")[:300]}', flush=True)
    print(f'Sources: {body.get("sources", "N/A")}', flush=True)
    qu = body.get('query_understanding')
    if qu:
        print(f'\nQuery Understanding:', flush=True)
        print(f'  Intent: {qu.get("intent", "N/A")}', flush=True)
        print(f'  Rewritten: {qu.get("rewritten_query", "N/A")}', flush=True)
        print(f'  Expanded: {qu.get("expanded_query", "N/A")}', flush=True)
        print(f'  Decomposed: {qu.get("decomposed_queries", "N/A")}', flush=True)
except urllib.error.HTTPError as e:
    print(f'HTTP Error {e.code}: {e.read().decode()[:500]}', flush=True)
except Exception as e:
    print(f'FAILED: {e}', flush=True)
