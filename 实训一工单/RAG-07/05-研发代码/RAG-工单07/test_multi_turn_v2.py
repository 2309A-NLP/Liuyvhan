"""测试多轮对话 — 用新的 conversation_id 避免缓存干扰"""
import requests, json, sys

BASE = "http://localhost:8001/api/v1"
CID = "multi-turn-v2"  # 新 ID，避免旧缓存

def ask(q, cid=None):
    payload = {"question": q, "top_k": 3, "force_refresh": True}
    if cid:
        payload["conversation_id"] = cid
    r = requests.post(f"{BASE}/chat/rag", json=payload, timeout=120)
    data = r.json()
    qu = data.get("query_understanding", {})
    print(f"Q: {q}")
    print(f"  CID: {data.get('conversation_id')}")
    print(f"  query_type: {qu.get('query_type')}")
    print(f"  rewritten: {qu.get('rewritten_query')}")
    print(f"  A: {data.get('answer', '')[:150]}")
    print("-" * 50)
    return data

print("=" * 60)
print("第1轮: 国家科技进步一等奖")
print("=" * 60)
r1 = ask("他参与的哪个工程荣获了国家科技进步一等奖？", CID)

print("=" * 60)
print("第2轮: 法定代表人（完整问句）")
print("=" * 60)
r2 = ask("这个公司的法定代表人是谁？", CID)

print("=" * 60)
print("第3轮: 省略问句（关键词测试）")
print("=" * 60)
r3 = ask("那武汉力源信息技术股份有限公司呢？", CID)

# 验证第3轮的 rewritten_query 是否正确还原了省略句
qu3 = r3.get("query_understanding", {})
rw3 = qu3.get("rewritten_query", "")
print("\n验证:")
print(f"  第3轮 rewritten: {rw3}")
has_context = "法定代表人" in rw3 or "法人" in rw3 or "公司" in rw3
print(f"  是否还原省略句: {'✅ 是' if has_context else '❌ 否'}")
