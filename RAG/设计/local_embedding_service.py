from __future__ import annotations

from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config import SETTINGS
from utils.logger import get_logger

logger = get_logger("local_embedding_service")
app = FastAPI(title="Local Embedding Service", version="1.0.0")


class EmbeddingRequest(BaseModel):
    model: str = Field(default="moka-ai/m3e-base")
    input: list[str]


class EmbeddingItem(BaseModel):
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    data: list[EmbeddingItem]


class LocalSentenceTransformerBackend:
    def __init__(self, model_path: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers is not installed. Install it before starting local embedding service."
            ) from exc

        if not model_path:
            raise RuntimeError("LOCAL_EMBEDDING_MODEL_PATH is empty.")

        logger.info("Loading local embedding model from %s", model_path)
        self.model = SentenceTransformer(model_path, device="cpu")
        logger.info("Local embedding model loaded from %s", model_path)

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        matrix = np.asarray(embeddings, dtype="float32")
        if matrix.ndim == 1:
            matrix = np.expand_dims(matrix, axis=0)
        return matrix.tolist()


backend: LocalSentenceTransformerBackend | None = None


@app.on_event("startup")
def load_model() -> None:
    global backend
    backend = LocalSentenceTransformerBackend(SETTINGS.local_embedding_model_path)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model_path": SETTINGS.local_embedding_model_path,
        "model_name": SETTINGS.embedding_model_name,
        "dimension": SETTINGS.embedding_dimension,
    }


@app.post("/embeddings", response_model=EmbeddingResponse)
def embeddings(payload: EmbeddingRequest) -> EmbeddingResponse:
    if backend is None:
        raise HTTPException(status_code=503, detail="Embedding model is not loaded.")
    if not payload.input:
        return EmbeddingResponse(data=[])

    vectors = backend.encode(payload.input)
    return EmbeddingResponse(data=[EmbeddingItem(embedding=vector) for vector in vectors])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "local_embedding_service:app",
        host=SETTINGS.local_embedding_service_host,
        port=SETTINGS.local_embedding_service_port,
        reload=False,
    )
