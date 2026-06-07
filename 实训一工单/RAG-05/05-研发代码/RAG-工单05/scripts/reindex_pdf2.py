"""仅重建招股说明书2.pdf（力源信息，含组织结构图）"""
import sys, os, time

os.chdir(r"C:\Users\刘禹含\Desktop\RAG-工单04")
sys.path.insert(0, r"C:\Users\刘禹含\Desktop\RAG-工单04")
os.environ["HF_HUB_OFFLINE"] = "1"

print("[START] 开始加载模块...", flush=True)
from app.core.container import container
from app.core.config import settings
from pathlib import Path

print(f"[OK] 模型: {settings.multimodal_model}", flush=True)
print(f"[OK] VLM启用: {settings.enable_vlm_image_semantics}", flush=True)
print(f"[OK] CLIP启用: {settings.enable_clip_image_semantics}", flush=True)

target = "招股说明书2.pdf"
file_path = settings.raw_dir / target
print(f"[INFO] 仅处理: {target}", flush=True)

started = time.perf_counter()
result = container.rag_service.ingest_file(file_path=file_path, rebuild=True)
elapsed = round(time.perf_counter() - started, 3)

print(f"\n{'='*50}", flush=True)
print(f"[OK] 索引完成！", flush=True)
print(f"  文件: {result.get('file_name')}", flush=True)
print(f"  DocID: {result.get('doc_id')}", flush=True)
print(f"  页数: {result.get('pages')}", flush=True)
print(f"  Chunks: {result.get('chunks')}", flush=True)
print(f"  耗时: {elapsed}s", flush=True)
print(f"{'='*50}", flush=True)
