"""Test reranker loading from local cache"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

from sentence_transformers import CrossEncoder

# Try 1: model name
print('Test 1: CrossEncoder(model_name, local_files_only=True)', flush=True)
try:
    model = CrossEncoder('BAAI/bge-reranker-v2-m3', local_files_only=True)
    print('  OK!', flush=True)
except Exception as e:
    print(f'  FAIL: {e}', flush=True)

# Try 2: local snapshot path
import json
hub_root = os.path.expanduser('~/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3/snapshots')
import glob
snapshots = sorted(glob.glob(os.path.join(hub_root, '*')))
if snapshots:
    path = snapshots[-1]
    print(f'\nTest 2: CrossEncoder(snapshot_path={path})', flush=True)
    try:
        model = CrossEncoder(path, local_files_only=True)
        print('  OK!', flush=True)
        # Test prediction
        scores = model.predict([['发了几股', '本次发行股数']])
        print(f'  Predict OK: {scores}', flush=True)
    except Exception as e:
        print(f'  FAIL: {e}', flush=True)
else:
    print(f'No snapshots found in {hub_root}', flush=True)
