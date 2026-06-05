from app.core.config import settings
from app.services.cache_service import CacheService
from app.services.bm25_service import BM25Service
from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService
from app.services.evaluation_service import EvaluationService
from app.services.feedback_service import FeedbackService
from app.services.llm_service import LLMService
from app.services.pdf_service import PDFService
from app.services.query_enhancer_service import QueryEnhancerService
from app.services.rag_service import RAGService
from app.services.reranker_service import RerankerService
from app.services.vector_store import MilvusVectorStore


class ServiceContainer:
    def __init__(self) -> None:
        self.pdf_service = PDFService()
        self.chunk_service = ChunkService()
        self.bm25_service = BM25Service()
        self.embedding_service = EmbeddingService()
        self.query_enhancer_service = QueryEnhancerService()
        self.reranker_service = RerankerService()
        self.vector_store = MilvusVectorStore(self.embedding_service.embedding_dimension)
        self.cache_service = CacheService()
        self.llm_service = LLMService()
        self.feedback_service = FeedbackService()
        self.rag_service = RAGService(
            pdf_service=self.pdf_service,
            chunk_service=self.chunk_service,
            bm25_service=self.bm25_service,
            embedding_service=self.embedding_service,
            query_enhancer_service=self.query_enhancer_service,
            reranker_service=self.reranker_service,
            vector_store=self.vector_store,
            cache_service=self.cache_service,
            llm_service=self.llm_service,
        )
        self.evaluation_service = EvaluationService(
            rag_service=self.rag_service,
            llm_service=self.llm_service,
        )
        self._restore_bm25_indexes()

    def _restore_bm25_indexes(self) -> None:
        for chunks_file in settings.processed_dir.glob("*_chunks.json"):
            self.bm25_service.restore_from_chunks_file(chunks_file)
        self._ensure_milvus_populated()

    def _ensure_milvus_populated(self) -> None:
        """启动时检查 Milvus，如果为空则从本地 chunks 重新导入。"""
        if not self.vector_store.available:
            return
        import json
        for chunks_file in sorted(settings.processed_dir.glob("*_chunks.json")):
            try:
                chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
                if not chunks:
                    continue
                file_name = chunks[0]["file_name"]
                doc_id = chunks[0]["doc_id"]
                # 检查 Milvus 是否已有此文档
                results = self.vector_store.client.query(
                    collection_name=self.vector_store.collection_name,
                    filter=f'doc_id == "{doc_id}"',
                    output_fields=["chunk_id"],
                    limit=1,
                )
                if len(results) > 0:
                    continue  # 已在 Milvus 中
            except Exception:
                continue
            # Milvus 缺失该文档 → 重新索引
            file_path = self.rag_service.resolve_file_path(file_name)
            self.rag_service.ingest_file(file_path=file_path, rebuild=False)


container = ServiceContainer()
