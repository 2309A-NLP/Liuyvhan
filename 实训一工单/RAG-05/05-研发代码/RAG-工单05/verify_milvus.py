"""Test Milvus connection from Windows Anaconda with the new URI"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pymilvus import MilvusClient

uri = "http://172.18.224.39:19530"
print(f'Connecting to Milvus at: {uri}', flush=True)

c = MilvusClient(uri=uri)
collections = c.list_collections()
print(f'Collections: {collections}', flush=True)

if collections:
    for col in collections:
        count = c.query(collection_name=col, filter='', output_fields=['count(*)'])
        print(f'  {col}: {count}', flush=True)
else:
    print('No collections exist yet (first indexing will create them)', flush=True)
