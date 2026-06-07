import sys
sys.stdout.reconfigure(encoding='utf-8')
try:
    import app.core.container
    print("Import OK: container loaded")
    print(f"Index ready: {app.core.container.container._index_ready_event.is_set()}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
