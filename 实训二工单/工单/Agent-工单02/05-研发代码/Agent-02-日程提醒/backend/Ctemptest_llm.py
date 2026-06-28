import urllib.request
import json

# Test with LLM - use natural language
data = json.dumps({"message": "明天早上8点提醒我起床"}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8012/chat",
    data=data,
    headers={"Content-Type": "application/json"}
)
try:
    resp = urllib.request.urlopen(req, timeout=15)
    result = json.loads(resp.read())
    print("=== LLM Response ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
