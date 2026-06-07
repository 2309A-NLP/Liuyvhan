"""仅重建招股说明书2.pdf（力源信息，含组织结构图）- 增强版，日志写入文件"""
import sys, os, time, traceback

# 设置日志
log_path = r"C:\Users\刘禹含\Desktop\RAG-工单04\reindex_pdf2_v4.log"
log_f = open(log_path, "w", encoding="utf-8")

def log(msg, also_print=True):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    log_f.write(line + "\n")
    log_f.flush()
    if also_print:
        print(line, flush=True)

log("=== 开始 reindex 招股说明书2.pdf ===")

try:
    os.chdir(r"C:\Users\刘禹含\Desktop\RAG-工单04")
    sys.path.insert(0, r"C:\Users\刘禹含\Desktop\RAG-工单04")
    os.environ["HF_HUB_OFFLINE"] = "1"

    log("加载模块...")
    from app.core.container import container
    from app.core.config import settings
    log(f"模型: {settings.multimodal_model}")
    log(f"VLM启用: {settings.enable_vlm_image_semantics}")

    target = "招股说明书2.pdf"
    file_path = settings.raw_dir / target
    log(f"处理: {target}")
    
    # 验证文件存在
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    log(f"文件大小: {os.path.getsize(file_path) / 1024 / 1024:.1f} MB")

    started = time.perf_counter()
    result = container.rag_service.ingest_file(file_path=file_path, rebuild=True)
    elapsed = round(time.perf_counter() - started, 3)

    log(f"\n{'='*50}")
    log(f"索引完成！")
    log(f"  文件: {result.get('file_name')}")
    log(f"  DocID: {result.get('doc_id')}")
    log(f"  页数: {result.get('pages')}")
    log(f"  Chunks: {result.get('chunks')}")
    log(f"  耗时: {elapsed}s")
    log(f"{'='*50}")

except Exception as e:
    tb = traceback.format_exc()
    log(f"错误: {e}")
    for line in tb.split("\n"):
        log(line, also_print=False)
    log("=== 异常终止 ===")
    sys.exit(1)

finally:
    log_f.close()

log("=== 正常完成 ===")
