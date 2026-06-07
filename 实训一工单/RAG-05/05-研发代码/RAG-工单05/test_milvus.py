import sys, json
sys.stdout.reconfigure(encoding='utf-8')

# Test 1: connect to 127.0.0.1:19530 (current config - Windows localhost)
from pymilvus import MilvusClient

print("=== Test 1: 127.0.0.1:19530 (Windows localhost) ===", flush=True)
try:
    c1 = MilvusClient(uri="http://127.0.0.1:19530")
    c1.list_collections()
    print("  OK! Connected to 127.0.0.1:19530", flush=True)
except Exception as e:
    print(f"  FAIL: {e}", flush=True)

# Test 2: connect to 172.18.224.1:19530 (WSL2 gateway IP - Windows side sees WSL via this IP)
print("=== Test 2: 172.18.224.1:19530 (WSL2 gateway IP) ===", flush=True)
try:
    c2 = MilvusClient(uri="http://172.18.224.1:19530")
    c2.list_collections()
    print("  OK! Connected to 172.18.224.1:19530", flush=True)
except Exception as e:
    print(f"  FAIL: {e}", flush=True)

# Test 3: connect with gRPC to 172.18.224.1
print("=== Test 3: 172.18.224.1:19530 (plain gRPC - no http prefix) ===", flush=True)
try:
    c3 = MilvusClient(uri="172.18.224.1:19530")
    c3.list_collections()
    print("  OK! Connected to 172.18.224.1:19530 (gRPC)", flush=True)
except Exception as e:
    print(f"  FAIL: {e}", flush=True)
