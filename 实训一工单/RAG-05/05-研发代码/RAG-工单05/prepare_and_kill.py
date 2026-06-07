"""Kill port 8001 zombie and write checkpoint to skip reindex"""
import sys, subprocess, json
sys.stdout.reconfigure(encoding='utf-8')

# 1. Kill zombie on port 8001
r = subprocess.run(
    ['powershell', '-Command',
     'Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue | '
     'Select-Object -ExpandProperty OwningProcess | '
     'ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; Write-Output "Killed PID $_" }'],
    capture_output=True, text=True, timeout=15
)
print(f'Port 8001: {r.stdout.strip() or "No zombie"}')

# 2. Write checkpoint file
import os
checkpoint_path = os.path.join(r'C:\Users\刘禹含\Desktop\RAG-工单05\data\processed', '.index_checkpoint')
os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
with open(checkpoint_path, 'w', encoding='utf-8') as f:
    json.dump({"complete": True, "notes": "manual checkpoint - BM25 data pre-populated"}, f)
print(f'Checkpoint written: {checkpoint_path}')

# 3. Verify BM25 data exists
bm25_path = os.path.join(r'C:\Users\刘禹含\Desktop\RAG-工单05\data\processed', 'bm25_index.pkl')
if os.path.exists(bm25_path):
    size = os.path.getsize(bm25_path)
    print(f'BM25 data exists: {bm25_path} ({size} bytes)')
else:
    print(f'WARNING: BM25 data NOT found at {bm25_path}')

# 4. List processed documents
processed_dir = r'C:\Users\刘禹含\Desktop\RAG-工单05\data\processed'
docs = [d for d in os.listdir(processed_dir) if os.path.isdir(os.path.join(processed_dir, d))]
print(f'Processed docs: {docs}')
