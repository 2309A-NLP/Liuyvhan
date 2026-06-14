import sys
sys.stdout.reconfigure(encoding='utf-8')
try:
    from app.core.config import settings
    print("OK - settings loaded")
    print(f"PORT: {settings.app_port}")
    print(f"MILVUS: {settings.milvus_uri}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
