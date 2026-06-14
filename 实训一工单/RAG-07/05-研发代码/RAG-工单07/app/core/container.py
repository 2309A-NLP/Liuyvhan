import json
import threading
import time
from pathlib import Path

from app.core.config import settings
from app.services.cache_service import CacheService
from app.services.bm25_service import BM25Service
from app.services.chunk_service import ChunkService
from app.services.conversation_store import ConversationStore
from app.services.embedding_service import EmbeddingService
from app.services.evaluation_service import EvaluationService
from app.services.feedback_service import FeedbackService
from app.services.image_semantic_service import ImageSemanticService
from app.services.llm_service import LLMService
from app.services.pdf_service import PDFService
from app.services.query_enhancer_service import QueryEnhancerService
from app.services.rag_service import RAGService
from app.services.reranker_service import RerankerService
from app.services.vector_store import MilvusVectorStore


class ServiceContainer:
    def __init__(self) -> None:
        self.image_semantic_service = ImageSemanticService()
        self.pdf_service = PDFService(image_semantic_service=self.image_semantic_service)
        self.chunk_service = ChunkService()
        self.bm25_service = BM25Service()
        self.embedding_service = EmbeddingService()
        self.embedding_service.ensure_initialized()
        self.llm_service = LLMService()
        self.query_enhancer_service = QueryEnhancerService(llm_service=self.llm_service)
        self.conversation_store = ConversationStore()
        self.reranker_service = RerankerService()
        # 不预加载 reranker（启动时加载会在首请求触发，避免启动阻塞）
        self.vector_store = MilvusVectorStore(self.embedding_service.embedding_dimension)
        self.cache_service = CacheService()
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
            conversation_store=self.conversation_store,
        )
        self.evaluation_service = EvaluationService(
            rag_service=self.rag_service,
            llm_service=self.llm_service,
        )
        self._restore_bm25_indexes()

        # ===== 工单05: 断点续传 + 后台索引 + 容器重启恢复 =====
        self._checkpoint_path = settings.processed_dir / ".index_checkpoint"
        self._index_lock = threading.Lock()
        self._index_in_progress = False
        self._index_ready_event = threading.Event()

        # 加载 checkpoint → 确定是否已经索引完成
        if self._load_checkpoint():
            self._index_ready_event.set()
            print("  [CHECKPOINT] 索引已完成，跳过后台索引", flush=True)
        else:
            # 启动后台索引线程（不阻塞服务器启动 + 不阻塞 RAG 请求）
            thr = threading.Thread(target=self._background_index, daemon=True, name="bg-index")
            thr.start()

    # ------------------------------------------------------------------
    # Checkpoint 读写
    # ------------------------------------------------------------------
    def _load_checkpoint(self) -> bool:
        """加载 checkpoint，返回索引是否完整。"""
        if not self._checkpoint_path.exists():
            return False
        try:
            data = json.loads(self._checkpoint_path.read_text(encoding="utf-8"))
            return data.get("complete", False)
        except Exception:
            return False

    def _write_checkpoint(self) -> None:
        """写入 checkpoint，记录已索引的文档。"""
        indexed_files: list[str] = []
        for mf in sorted(settings.processed_dir.glob("*_manifest.json")):
            try:
                manifest = json.loads(mf.read_text(encoding="utf-8"))
                if manifest.get("file_name"):
                    indexed_files.append(manifest["file_name"])
            except Exception:
                continue
        all_pdfs = list(settings.raw_dir.glob("*.pdf"))
        num_pdfs = len(all_pdfs)
        data = {
            "complete": num_pdfs > 0 and len(indexed_files) >= num_pdfs,
            "indexed_files": indexed_files,
            "total_pdfs": num_pdfs,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._checkpoint_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [CHECKPOINT] 已写入: complete={data['complete']} ({len(indexed_files)}/{num_pdfs})", flush=True)

    # ------------------------------------------------------------------
    # 后台索引（线程）→ 不阻塞 uvicorn 事件循环
    # ------------------------------------------------------------------
    def _background_index(self) -> None:
        """后台索索引线程：等待 Milvus 就绪 → 全量检查/索索引 → 写 checkpoint。"""
        with self._index_lock:
            if self._index_ready_event.is_set():
                return
            self._index_in_progress = True
            print("  [INDEX-BG] 后台索索引线程启动...", flush=True)

            # 重试等待 Milvus 就绪（Docker 启动有延迟）
            for attempt in range(6):
                if self.vector_store.available:
                    print(f"  [INDEX-BG] Milvus 已就绪 (attempt {attempt + 1})", flush=True)
                    break
                print(f"  [INDEX-BG] 等待 Milvus 就绪... ({attempt + 1}/6)", flush=True)
                time.sleep(5)
            else:
                print("  [INDEX-BG] Milvus 不可用，跳过后台索引", flush=True)
                self._index_in_progress = False
                return

            try:
                self._ensure_milvus_populated()
                self._write_checkpoint()
                self._index_ready_event.set()
                print("  [INDEX-BG] 后台索索引完成!", flush=True)
            except Exception as exc:
                print(f"  [INDEX-BG] 后台索索引失败: {exc}", flush=True)
            finally:
                self._index_in_progress = False

    # ------------------------------------------------------------------
    # Milvus 索引检查与恢复（带重试 + checkpoint 短路）
    # ------------------------------------------------------------------
    def _ensure_milvus_populated(self) -> None:
        """检查 Milvus，如果为空则从本地 chunks 重新导入。

        工单05 改进:
        - checkpoint 短路: 如果已标记完成，直接跳过
        - Milvus 查询重试: 应对 Docker 容器未就绪
        - 进度持久化: 每个文档索索引完成后写 checkpoint
        """
        # 快速路径：checkpoint 已确认所有文档都索引完成
        if self._index_ready_event.is_set():
            return
        if not self.vector_store.available:
            return

        for chunks_file in sorted(settings.processed_dir.glob("*_chunks.json")):
            try:
                chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not chunks:
                continue
            file_name = chunks[0]["file_name"]
            doc_id = chunks[0]["doc_id"]

            # 带重试的 Milvus 查询（应对容器启动延迟）
            already_in_milvus = False
            for retry in range(3):
                try:
                    results = self.vector_store.client.query(
                        collection_name=self.vector_store.collection_name,
                        filter=f'doc_id == "{doc_id}"',
                        output_fields=["chunk_id"],
                        limit=1,
                    )
                    if len(results) > 0:
                        already_in_milvus = True
                    break  # 查询成功 → 跳出重试循环
                except Exception as e:
                    if retry < 2:
                        print(f"  [MILVUS] 查询失败 {e}, 重试 {retry + 1}/3...", flush=True)
                        time.sleep(3)
                    else:
                        print(f"  [MILVUS] 查询失败 3次, 跳过 {file_name}: {e}", flush=True)

            if already_in_milvus:
                print(f"  [MILVUS] 已存在: {file_name} (doc_id={doc_id})", flush=True)
                continue

            # Milvus 缺失 → 重新索索引
            print(f"  [MILVUS] 缺失, 重新索索引: {file_name}", flush=True)
            try:
                file_path = self.rag_service.resolve_file_path(file_name)
                self.rag_service.ingest_file(file_path=file_path, rebuild=False)
                # 每个文档索索引完成后写入 checkpoint（部分进度）
                self._write_checkpoint()
            except Exception as exc:
                print(f"  [MILVUS] 索索引失败 {file_name}: {exc}", flush=True)

    # ------------------------------------------------------------------
    # BM25 索引恢复（使用已有 chunks 文件）
    # ------------------------------------------------------------------
    def _restore_bm25_indexes(self) -> None:
        """启动时从已保存的 chunks 文件恢复 BM25 索引。"""
        for manifest_file in sorted(settings.processed_dir.glob("*_manifest.json")):
            try:
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                file_name = manifest.get("file_name")
                chunk_path = manifest.get("chunk_manifest_path")
                if not file_name or not chunk_path:
                    continue
                chunk_file = Path(chunk_path)
                if not chunk_file.exists():
                    continue
                self.bm25_service.restore_from_chunks_file(chunk_file)
                print(f"  [BM25] 已恢复: {file_name} ({manifest.get('chunks', '?')} chunks)", flush=True)
            except Exception as exc:
                print(f"  [BM25] 恢复失败: {exc}", flush=True)


container = ServiceContainer()
