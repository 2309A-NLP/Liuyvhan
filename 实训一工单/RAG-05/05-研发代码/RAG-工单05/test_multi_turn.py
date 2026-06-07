"""测试多轮对话"""
import requests, json

BASE = "http://localhost:8001/api/v1"
CID = "test-001"

def ask(q, cid=None):
    payload = {"question": q, "top_k": 3}
    if cid:
        payload["conversation_id"] = cid
    r = requests.post(f"{BASE}/chat/rag", json=payload, timeout=60)
    data = r.json()
    print(f"Q: {q}")
    print(f"CID: {data.get('conversation_id')}")
    print(f"query_understanding:")
    qu = data.get("query_understanding", {})
    print(f"  query_type: {qu.get('query_type')}")
    print(f"  rewritten: {qu.get('rewritten_query')}")
    print(f"  expanded: {qu.get('expanded_query')[:80]}...")
    print(f"  sub_queries: {qu.get('sub_queries')}")
    print(f"A: {data.get('answer', '')[:120]}")
    print("-" * 50)
    return data

# 第1轮
print("=== 第1轮 ===")
r1 = ask("他参与的哪个工程荣获了国家科技进步一等奖？", CID)

# 第2轮
print("\n=== 第2轮 ===")
r2 = ask("这个公司的法定代表人是谁？", CID)

# 第3轮 — 省略问句（依赖前一轮context）
print("\n=== 第3轮（省略问句）===")
r3 = ask("那武汉力源信息技术股份有限公司呢？", CID)
