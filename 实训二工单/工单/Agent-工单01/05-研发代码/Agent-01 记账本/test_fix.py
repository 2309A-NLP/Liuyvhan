"""测试修复是否生效"""
import sys, json
from datetime import date, datetime
sys.path.insert(0, ".")

print("=== 测试1: _prepare_data_for_json ===")
# 模拟agent.py的_prepare_data_for_json逻辑
data = {
    "record_date": date(2026, 6, 16),
    "member": "女儿",
    "type": "支出",
    "category": "通讯",
    "item": "流量卡",
    "amount": 50.0
}

json_data = {}
for k, v in data.items():
    if isinstance(v, date):
        json_data[k] = v.strftime("%Y-%m-%d")
    else:
        json_data[k] = v

result = {"type": "confirm_add", "content": "测试内容", "data": json_data}
try:
    dumped = json.dumps(result, ensure_ascii=False, allow_nan=False)
    print("  PASS: JSON序列化成功")
    print(f"  data.record_date = {json_data['record_date']} (type: {type(json_data['record_date']).__name__})")
except TypeError as e:
    print(f"  FAIL: {e}")

print()
print("=== 测试2: 旧版bug（date对象直接返回）===")
result_raw = {"type": "confirm_add", "content": "测试", "data": data}
try:
    json.dumps(result_raw, ensure_ascii=False, allow_nan=False)
    print("  UNEXPECTED PASS - 说明漏洞没复现？")
except TypeError as e:
    print(f"  EXPECTED FAIL: {e}")

print()
print("=== 测试3: 直接测试main.py的agent ===")
from agent import AccountBookAgent
agent = AccountBookAgent()

# 测试第一条消息
resp = agent.process_message("女儿今天冲了一张流量卡 花了50元")
print(f"  类型: {resp['type']}")
print(f"  内容: {resp['content']}")
# 测试能否序列化
try:
    dumped = json.dumps(resp, ensure_ascii=False, allow_nan=False)
    print("  序列化: PASS")
except TypeError as e:
    print(f"  序列化: FAIL - {e}")

print()
print("=== 测试4: 第二条消息（确认）===")
resp2 = agent.process_message("确认")
print(f"  类型: {resp2['type']}")
print(f"  内容: {resp2['content']}")
try:
    dumped = json.dumps(resp2, ensure_ascii=False, allow_nan=False)
    print("  序列化: PASS")
except TypeError as e:
    print(f"  序列化: FAIL - {e}")

print()
print("=== 测试5: 第二条新记录（新agent实例）===")
agent2 = AccountBookAgent()
resp3 = agent2.process_message("妈妈今天买菜花了20元")
print(f"  类型: {resp3['type']}")
print(f"  内容: {resp3['content']}")
try:
    dumped = json.dumps(resp3, ensure_ascii=False, allow_nan=False)
    print("  序列化: PASS")
except TypeError as e:
    print(f"  序列化: FAIL - {e}")

print()
print("=== 全部测试完成 ===")
