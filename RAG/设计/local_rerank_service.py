from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import SETTINGS
from utils.logger import get_logger

logger = get_logger("local_rerank_service")
app = FastAPI(title="Local Rerank Service", version="1.0.0")


class RerankRequest(BaseModel):
    model: str = Field(default="BAAI/bge-reranker-v2-m3")
    query: str
    documents: list[str]
    top_n: int = 4


class RerankItem(BaseModel):
    index: int
    relevance_score: float


class RerankResponse(BaseModel):
    results: list[RerankItem]


class LocalRerankBackend:
    def __init__(self, model_path: str):
        self.model_path = model_path.strip()
        self.model = None
        self.backend = "heuristic"

        if self.model_path:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "sentence-transformers is not installed. Install it before starting rerank service."
                ) from exc

            try:
                logger.info("Loading local rerank model from %s", self.model_path)
                self.model = CrossEncoder(self.model_path, device="cpu")
                self.backend = "cross_encoder"
                logger.info("Local rerank model loaded from %s", self.model_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to load rerank model from %s, fallback to heuristic mode. error=%s",
                    self.model_path,
                    exc,
                )
        else:
            logger.warning("Local rerank model path is empty, fallback to heuristic mode.")

    def score(self, query: str, documents: list[str]) -> list[float]:
        if self.model is not None:
            pairs = [(query, doc) for doc in documents]
            scores = self.model.predict(
                pairs,
                batch_size=8,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return [float(score) for score in scores]

        query_terms = self._tokenize(query)
        query_set = set(query_terms)
        scores: list[float] = []
        for doc in documents:
            doc_terms = set(self._tokenize(doc))
            overlap = len(query_set & doc_terms) / max(len(query_set), 1)
            phrase_bonus = 0.0
            if query and query.lower() in doc.lower():
                phrase_bonus = 0.15
            length_penalty = min(len(doc) / 4000.0, 0.1)
            scores.append(max(0.0, overlap + phrase_bonus - length_penalty))
        return scores

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
        words = [word for word in cleaned.split() if word]
        dense = "".join(words)
        tokens = words + [dense[i : i + 2] for i in range(max(1, len(dense) - 1))] if dense else []
        return tokens or [text[i : i + 2] for i in range(max(1, len(text) - 1))]


backend: LocalRerankBackend | None = None


@app.on_event("startup")
def load_model() -> None:
    global backend
    backend = LocalRerankBackend(SETTINGS.local_rerank_model_path)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model_path": SETTINGS.local_rerank_model_path,
        "model_name": SETTINGS.rerank_model_name,
        "backend": backend.backend if backend else "unloaded",
    }


@app.post("/rerank", response_model=RerankResponse)
def rerank(payload: RerankRequest) -> RerankResponse:
    if backend is None:
        raise HTTPException(status_code=503, detail="Rerank model is not loaded.")
    if not payload.documents:
        return RerankResponse(results=[])

    scores = backend.score(payload.query, payload.documents)
    ranked = sorted(
        (
            {"index": idx, "relevance_score": float(score)}
            for idx, score in enumerate(scores)
        ),
        key=lambda item: item["relevance_score"],
        reverse=True,
    )
    return RerankResponse(results=[RerankItem(**item) for item in ranked[: payload.top_n]])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "local_rerank_service:app",
        host=SETTINGS.local_rerank_service_host,
        port=SETTINGS.local_rerank_service_port,
        reload=False,
    )
