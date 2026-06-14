import hashlib
import math
from pathlib import Path

from sentence_transformers import SentenceTransformer

from app.core.config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self.model = None
        self.embedding_dimension = 384
        self.model_name = settings.embedding_model
        self.model_path = settings.embedding_model_path.strip()
        self.loaded_from = "fallback"
        self._initialized = False

    def _init_model(self) -> None:
        local_path = Path(self.model_path) if self.model_path else None

        if local_path and local_path.exists():
            try:
                # 人工智能 NLP-RAG-基于 PDF文档的问答系统 优先加载用户指定的本地嵌入模型，提升中文长文档检索效果。
                self.model = SentenceTransformer(str(local_path), local_files_only=True)
                self.embedding_dimension = self.model.get_sentence_embedding_dimension()
                self.loaded_from = str(local_path)
                return
            except Exception:
                self.model = None

        try:
            # 人工智能 NLP-RAG-基于 PDF文档的问答系统 在本地模型路径不可用时，回退到配置中的模型名称。
            self.model = SentenceTransformer(self.model_name, local_files_only=True)
            self.embedding_dimension = self.model.get_sentence_embedding_dimension()
            self.loaded_from = self.model_name
        except Exception:
            self.model = None
            self.loaded_from = "fallback"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self._ensure_initialized()
        if self.model is not None:
            batch_size = settings.embedding_batch_size
            total_batches = (len(texts) + batch_size - 1) // batch_size
            print(f"    [EMBED] 共{len(texts)}条, 批次{batch_size}, {total_batches}批", flush=True)
            all_vectors = []
            for start_idx in range(0, len(texts), batch_size):
                batch = texts[start_idx : start_idx + batch_size]
                print(f"    [EMBED] 批 {start_idx//batch_size + 1}/{total_batches} ({len(batch)}条)...", flush=True)
                vectors = self.model.encode(
                    batch,
                    batch_size=batch_size,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                all_vectors.extend([vector.tolist() for vector in vectors])
                print(f"    [EMBED] 批完成 ({len(all_vectors)}/{len(texts)})", flush=True)
            return all_vectors

        return [self._fallback_embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def ensure_initialized(self) -> None:
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._init_model()
        self._initialized = True

    def _fallback_embed(self, text: str) -> list[float]:
        # 人工智能 NLP-RAG-基于 PDF文档的问答系统 在本地模型不可用时使用稳定哈希向量兜底，保证系统仍可运行。
        vector = [0.0] * self.embedding_dimension
        tokens = [token for token in text.lower().split() if token.strip()]
        if not tokens:
            tokens = list(text.strip()) or ["empty"]

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for offset in range(0, min(len(digest), 32), 2):
                index = int.from_bytes(digest[offset : offset + 2], "big") % self.embedding_dimension
                vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
