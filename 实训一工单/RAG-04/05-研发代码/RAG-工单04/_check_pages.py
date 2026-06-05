import json
from pathlib import Path

proc = Path("/mnt/c/Users/刘禹含/Desktop/RAG-工单04/data/processed")

# Check the old 17a1496c4852a904 chunks for company name
chunks = json.loads((proc / "17a1496c4852a904_chunks.json").read_text(encoding="utf-8"))
companies = set()
for c in chunks[:50]:
    content = c["content"][:200]
    if "力源" in content:
        companies.add("力源信息")
    if "兴图" in content:
        companies.add("兴图新科")

print(f"17a1496c4852a904 (333p, 715 chunks) mentions: {companies}")

# Check what content is at page 100 in BOTH versions
print("\n=== f521482a1de3de75 (PDF1 VLM, 548p) page 100 ===")
chunks1 = json.loads((proc / "f521482a1de3de75_chunks.json").read_text(encoding="utf-8"))
for c in chunks1:
    if c["page"] == 100:
        print(f"  [{c['chunk_index']}] type={c.get('block_type','?')}: {c['content'][:150]}")

print("\n=== 17a1496c4852a904 (old, 333p) page 100 ===")
for c in chunks:
    if c["page"] == 100:
        print(f"  [{c['chunk_index']}] type={c.get('block_type','?')}: {c['content'][:150]}")

# Also check what content PDF2 (力源信息) has at page 100
print("\n=== 499303a1a22ecd22 (PDF2, 力源信息) page 100 ===")
chunks3 = json.loads((proc / "499303a1a22ecd22_chunks.json").read_text(encoding="utf-8"))
for c in chunks3:
    if c["page"] == 100:
        print(f"  [{c['chunk_index']}] type={c.get('block_type','?')}: {c['content'][:150]}")
