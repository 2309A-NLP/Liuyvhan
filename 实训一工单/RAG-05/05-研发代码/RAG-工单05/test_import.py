"""Quick test: import the container to catch startup errors"""
import sys, traceback
sys.stdout.reconfigure(encoding='utf-8')

print('Testing container import...', flush=True)
try:
    from app.core.container import container
    print(f'OK! container created', flush=True)
    print(f'  BM25 docs: {len(container.bm25_service.indexes)}', flush=True)
    print(f'  Milvus available: {container.vector_store.available}', flush=True)
    print(f'  Reranker model: {container.reranker_service.model is not None}', flush=True)
    print(f'  Index ready: {container._index_ready_event.is_set()}', flush=True)
except Exception as e:
    traceback.print_exc()
    print(f'FAILED: {e}', flush=True)
