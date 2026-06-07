"""并行重建所有PDF索引（独立脚本，不依赖uvicorn）"""
import sys
import os
import time

# 确保路径正确
project_dir = r"C:\Users\刘禹含\Desktop\RAG-工单04"
os.chdir(project_dir)
sys.path.insert(0, project_dir)
os.environ["HF_HUB_OFFLINE"] = "1"

print("正在加载模块...", flush=True)
from app.core.container import container
from app.core.config import settings
from pathlib import Path

print(f"数据目录: {settings.raw_dir}", flush=True)

pdf_files = sorted(settings.raw_dir.glob("*.pdf"))
print(f"发现 {len(pdf_files)} 个 PDF:", flush=True)
for p in pdf_files:
    print(f"  {p.name}", flush=True)

if not pdf_files:
    print("没有找到PDF文件，退出。", flush=True)
    sys.exit(0)

print("\n开始并行重建索引...", flush=True)
print("(这包含CLIP图片分类 + GLM-4.1V多模态描述 + 向量嵌入，可能需要几分钟)", flush=True)

started = time.perf_counter()
try:
    results = container.rag_service.ingest_all_files(rebuild=True)
    elapsed = round(time.perf_counter() - started, 3)
    print(f"\n{'='*50}", flush=True)
    print(f"索引完成！总耗时: {elapsed} 秒", flush=True)
    for r in results:
        status = r["status"]
        name = r["file_name"]
        if status == "success":
            dur = r.get("duration_seconds", "N/A")
            print(f"  ✓ {name}: {r['pages']}页, {r['chunks']}chunks, {dur}s", flush=True)
        else:
            print(f"  ✗ {name}: 失败 - {r.get('error', '未知错误')}", flush=True)
except Exception as e:
    print(f"\n索引过程中出错: {e}", flush=True)
    import traceback
    traceback.print_exc()

print(f"\n完成时间: {time.strftime('%H:%M:%S')}", flush=True)
