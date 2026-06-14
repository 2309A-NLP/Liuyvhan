import json
from collections import Counter
from pathlib import Path

proc = Path("/mnt/c/Users/刘禹含/Desktop/RAG-工单04/data/processed")

for mf in proc.glob("*_manifest.json"):
    m = json.loads(mf.read_text(encoding="utf-8"))
    print(f"Manifest: {mf.name}")
    for k, v in m.items():
        print(f"  {k}: {v}")
    print()

# PDF1 VLM version (1698 chunks)
chunks = json.loads((proc / "f521482a1de3de75_chunks.json").read_text(encoding="utf-8"))
print(f"=== PDF1 VLM version: {len(chunks)} chunks ===")

print("\nFirst 15 chunks:")
for i, c in enumerate(chunks[:15]):
    typ = c.get("block_type", "?")
    ct = c["content"][:120]
    print(f"  [{i}] page={c['page']} type={typ} chunk_idx={c['chunk_index']} content=\"{ct}\"")

print("\nPage distribution (first 30 pages):")
page_counts = Counter(c["page"] for c in chunks)
for p in sorted(page_counts.keys())[:30]:
    print(f"  Page {p}: {page_counts[p]} chunks")

print(f"\nPage range: {min(c['page'] for c in chunks)} to {max(c['page'] for c in chunks)}")

# Check the "page 100" chunk where images are
print("\n=== Chunks near page 100 ===")
for c in chunks:
    if c["page"] == 100:
        print(f"  type={c.get('block_type','?')} chunk_idx={c['chunk_index']} content={c['content'][:200]}")

# Check PDF2 (17a1496c4852a904)
chunks2 = json.loads((proc / "17a1496c4852a904_chunks.json").read_text(encoding="utf-8"))
print(f"\n=== PDF2 VLM version: {len(chunks2)} chunks ===")
print("First 10 chunks:")
for i, c in enumerate(chunks2[:10]):
    typ = c.get("block_type", "?")
    ct = c["content"][:120]
    print(f"  [{i}] page={c['page']} type={typ} chunk_idx={c['chunk_index']} content=\"{ct}\"")
