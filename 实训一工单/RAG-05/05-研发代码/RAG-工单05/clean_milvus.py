import sys
sys.path.insert(0, ".")
from pymilvus import connections, Collection

connections.connect(host="127.0.0.1", port="19530")
collection = Collection("prospectus_chunks")
collection.load()

results = collection.query(
    expr='file_name == "招股说明书2.pdf"',
    output_fields=["chunk_id"],
    limit=10,
)
print(f"Found {len(results)} vectors for this file")
if results:
    collection.delete('file_name == "招股说明书2.pdf"')
    print("Deleted old vectors")
collection.release()
