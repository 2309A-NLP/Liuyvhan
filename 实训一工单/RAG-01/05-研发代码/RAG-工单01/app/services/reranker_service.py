import os
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from sentence_transformers import CrossEncoder

from app.core.config import settings


class RerankerService:
    def __init__(self) -> None:
        self.model = None
        self.enabled = settings.enable_reranker
        self.model_name = settings.reranker_model
        self._init_model()

    def _init_model(self) -> None:
        if not self.enabled:
            return

        try:
            # 人工智能 NLP-RAG-基于 PDF文档的问答系统: 优先从本地缓存加载 reranker，避免受外网下载限制影响主流程。
            self.model = CrossEncoder(self.model_name, local_files_only=True)
            return
        except Exception:
            self.model = None

        local_snapshot = self._resolve_local_snapshot_path()
        if local_snapshot is None:
            return

        try:
            self.model = CrossEncoder(str(local_snapshot), local_files_only=True)
        except Exception:
            self.model = None

    def rerank(self, question: str, hits: list[dict], top_k: int | None = None) -> list[dict]:
        if self.model is None or not hits:
            return hits[: top_k or settings.reranker_top_k]

        top_k = top_k or settings.reranker_top_k
        sentence_pairs = [[question, item["content"]] for item in hits]
        scores = self.model.predict(sentence_pairs)

        reranked_hits: list[dict] = []
        for item, score in zip(hits, scores):
            enriched = dict(item)
            enriched["rerank_score"] = float(score)
            reranked_hits.append(enriched)

        reranked_hits.sort(key=lambda item: item["rerank_score"], reverse=True)
        final_hits = reranked_hits[:top_k]
        for item in final_hits:
            item["score"] = round(float(item["rerank_score"]), 6)
        return final_hits

    def _resolve_local_snapshot_path(self) -> Path | None:
        hub_root = Path.home() / ".cache" / "huggingface" / "hub" / "models--BAAI--bge-reranker-v2-m3" / "snapshots"
        if not hub_root.exists():
            return None

        snapshots = sorted([item for item in hub_root.iterdir() if item.is_dir()])
        if not snapshots:
            return None
        return snapshots[-1]
