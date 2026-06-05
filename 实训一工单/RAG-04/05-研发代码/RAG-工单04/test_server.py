"""启动uvicorn服务 - 详细调试"""
import sys, os
sys.path.insert(0, r"C:\Users\刘禹含\Desktop\RAG-工单04")
os.chdir(r"C:\Users\刘禹含\Desktop\RAG-工单04")

log_f = open(r"C:\Users\刘禹含\Desktop\RAG-工单04\server_uvicorn.log", "w", encoding="utf-8")
import time

def log(msg):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}\n"
    print(line.strip(), flush=True)
    log_f.write(line)
    log_f.flush()

log("开始启动...")

try:
    log("导入app.core.config...")
    from app.core.config import settings
    log(f"配置OK: {settings.multimodal_model}")

    log("导入app.services.image_semantic_service...")
    from app.services.image_semantic_service import ImageSemanticService
    log("ImageSemanticService导入OK")

    log("导入app.services.embedding_service...")
    from app.services.embedding_service import EmbeddingService
    log("EmbeddingService导入OK")

    log("导入剩下的服务模块...")
    from app.services.cache_service import CacheService
    from app.services.bm25_service import BM25Service
    from app.services.chunk_service import ChunkService
    from app.services.evaluation_service import EvaluationService
    from app.services.feedback_service import FeedbackService
    from app.services.llm_service import LLMService
    from app.services.pdf_service import PDFService
    from app.services.query_enhancer_service import QueryEnhancerService
    from app.services.rag_service import RAGService
    from app.services.reranker_service import RerankerService
    from app.services.vector_store import MilvusVectorStore
    from app.models.schemas import AskResponse
    log("所有模块导入OK")

    log("导入app.api.routes...")
    from app.api.routes import router
    log("routes导入OK")

    log("导入fastapi...")
    from fastapi import FastAPI
    log("fastapi导入OK")

    log("创建ServiceContainer...")
    log("  - ImageSemanticService()...")
    img_svc = ImageSemanticService()
    log("  - ImageSemanticService OK")

    log("  - PDFService()...")
    pdf_svc = PDFService(image_semantic_service=img_svc)
    log("  - PDFService OK")

    log("  - ChunkService()...")
    chunk_svc = ChunkService()
    log("  - ChunkService OK")

    log("  - BM25Service()...")
    bm25_svc = BM25Service()
    log("  - BM25Service OK")

    log("  - EmbeddingService()...")
    embed_svc = EmbeddingService()
    log("  - EmbeddingService OK")

    log("  - Ensuring embedding initialized (loads m3e-base model)...")
    embed_svc.ensure_initialized()
    log("  - Embedding initialized OK")

    log("  - QueryEnhancerService()...")
    qe_svc = QueryEnhancerService()
    log("  - RerankerService()...")
    rerank_svc = RerankerService()
    log("  - MilvusVectorStore()...")
    vec_store = MilvusVectorStore(embed_svc.embedding_dimension)
    log("  - CacheService()...")
    cache_svc = CacheService()
    log("  - LLMService()...")
    llm_svc = LLMService()

    log("  - RAGService()...")
    rag_svc = RAGService(
        pdf_service=pdf_svc, chunk_service=chunk_svc, bm25_service=bm25_svc,
        embedding_service=embed_svc, query_enhancer_service=qe_svc,
        reranker_service=rerank_svc, vector_store=vec_store,
        cache_service=cache_svc, llm_service=llm_svc,
    )
    log("  - FeedbackService()...")
    fb_svc = FeedbackService()
    log("  - EvaluationService()...")
    eval_svc = EvaluationService(rag_service=rag_svc, llm_service=llm_svc)
    log("ServiceContainer创建完成")

    log("创建FastAPI app...")
    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.include_router(router, prefix="/api/v1")
    log("FastAPI app创建完成")

except Exception as e:
    import traceback
    tb = traceback.format_exc()
    log(f"错误: {e}\n{tb}")
    log_f.close()
    sys.exit(1)

log("启动uvicorn...")
log_f.close()

import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
