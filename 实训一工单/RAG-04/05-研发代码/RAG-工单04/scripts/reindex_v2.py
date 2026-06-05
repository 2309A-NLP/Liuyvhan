"""并行重建所有PDF索引 v2 - 直接调用，输出到控制台"""
import sys
import os
import time

project_dir = r"C:\Users\刘禹含\Desktop\RAG-工单04"
os.chdir(project_dir)
sys.path.insert(0, project_dir)
os.environ["HF_HUB_OFFLINE"] = "1"

# 写日志到文件
log_file = os.path.join(project_dir, "reindex_v2.log")
def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")

log("正在加载模块...")
from app.core.container import container
from app.core.config import settings
from pathlib import Path

log(f"数据目录: {settings.raw_dir}")

pdf_files = sorted(settings.raw_dir.glob("*.pdf"))
log(f"发现 {len(pdf_files)} 个 PDF:")
for p in pdf_files:
    log(f"  {p.name}")

if not pdf_files:
    log("没有找到PDF文件，退出。")
    sys.exit(0)

log("")
log("开始并行重建索引...")
log(f"VLM模型: {settings.multimodal_model}")

# 检查VLM配置
log(f"LLM_BASE_URL: {settings.llm_base_url}")
log(f"LLM_API_KEY set: {bool(settings.llm_api_key)}")
log(f"ENABLE_VLM: {settings.enable_vlm_image_semantics}")
log(f"ENABLE_CLIP: {settings.enable_clip_image_semantics}")

started = time.perf_counter()
try:
    results = container.rag_service.ingest_all_files(rebuild=True)
    elapsed = round(time.perf_counter() - started, 3)
    log(f"\n{'='*50}")
    log(f"索引完成！总耗时: {elapsed} 秒")
    for r in results:
        status = r.get("status")
        name = r.get("file_name")
        if status == "success":
            dur = r.get("duration_seconds", "N/A")
            log(f"  ✓ {name}: {r.get('pages', '?')}页, {r.get('chunks', '?')}chunks, {dur}s")
        else:
            log(f"  ✗ {name}: 失败 - {r.get('error', '未知错误')}")
except Exception as e:
    log(f"\n索引过程中出错: {e}")
    import traceback
    traceback.print_exc()

log(f"\n完成时间: {time.strftime('%H:%M:%S')}")
