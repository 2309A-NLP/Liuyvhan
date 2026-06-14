import json
from pathlib import Path

proc = Path("/mnt/c/Users/刘禹含/Desktop/RAG-工单04/data/processed")

for cf in ["17a1496c4852a904", "f521482a1de3de75", "499303a1a22ecd22"]:
    chunks = json.loads((proc / f"{cf}_chunks.json").read_text(encoding="utf-8"))
    manifest = json.loads((proc / f"{cf}_manifest.json").read_text(encoding="utf-8"))
    first = chunks[0]["content"][:100]
    print(f"{cf}: manifest says file_name={manifest['file_name']}")
    print(f"  first chunk = \"{first}\"")
    print()
