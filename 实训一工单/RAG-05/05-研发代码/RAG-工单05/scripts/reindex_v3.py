"""并行重建所有PDF索引 v3 - 直接调用，所有输出重定向"""
import sys, os, time

os.chdir(r"C:\Users\刘禹含\Desktop\RAG-工单04")
sys.path.insert(0, r"C:\Users\刘禹含\Desktop\RAG-工单04")
os.environ["HF_HUB_OFFLINE"] = "1"

print("[START] 开始加载模块...", flush=True)
from app.core.container import container
from app.core.config import settings

print(f"[OK] 模型: {settings.multimodal_model}", flush=True)
print(f"[OK] VLM启用: {settings.enable_vlm_image_semantics}", flush=True)
print(f"[OK] CLIP启用: {settings.enable_clip_image_semantics}", flush=True)

pdf_files = sorted(settings.raw_dir.glob("*.pdf"))
print(f"[INFO] 发现 {len(pdf_files)} 个 PDF", flush=True)

started = time.perf_counter()
results = container.rag_service.ingest_all_files(rebuild=True)
elapsed = round(time.perf_counter() - started, 3)
print(f"\n[OK] 索引完成！耗时: {elapsed}s", flush=True)
for r in results:
    print(f"  {r.get('file_name')}: {r.get('status')} - {r.get('chunks')} chunks", flush=True)
