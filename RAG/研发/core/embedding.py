from __future__ import annotations

import numpy as np
import requests
from sklearn.feature_extraction.text import HashingVectorizer


class EmbeddingService:
    """Embedding service with remote-API support and local fallback."""

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.remote_url = settings.embedding_api_url.strip()
        self.backend = "remote_api" if self.remote_url else settings.embedding_backend
        self.vectorizer = HashingVectorizer(
            n_features=settings.embedding_dimension,
            analyzer="char_wb",
            ngram_range=(2, 4),
            alternate_sign=False,
            norm=None,
        )
        self.logger.info(
            "Embedding backend=%s, configured_model=%s, remote_enabled=%s",
            self.backend,
            settings.embedding_model_name,
            bool(self.remote_url),
        )

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.settings.embedding_dimension), dtype="float32")

        if self.remote_url:
            try:
                return self._embed_texts_remote(texts)
            except Exception as exc:
                self.logger.warning(
                    "Remote embedding failed, fallback to local hashing. error=%s",
                    exc,
                )

        return self._embed_texts_local(texts)

    def embed_text(self, text: str) -> np.ndarray:
        return self.embed_texts([text])[0]

    def _embed_texts_local(self, texts: list[str]) -> np.ndarray:
        matrix = self.vectorizer.transform(texts).toarray().astype("float32")
        return self._normalize(matrix)

    def _embed_texts_remote(self, texts: list[str]) -> np.ndarray:
        headers = {"Content-Type": "application/json"}
        if self.settings.embedding_api_key:
            headers["Authorization"] = f"Bearer {self.settings.embedding_api_key}"

        payload = {
            "model": self.settings.embedding_model_name,
            "input": texts,
        }
        endpoint = self.remote_url.rstrip("/")
        self.logger.info(
            "Calling embedding service model=%s endpoint=%s batch=%s",
            self.settings.embedding_model_name,
            endpoint,
            len(texts),
        )
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=self.settings.embedding_api_timeout,
        )
        response.raise_for_status()
        data = response.json()

        vectors = self._extract_vectors(data)
        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim != 2:
            raise RuntimeError("Embedding API returned invalid vector shape.")
        if matrix.shape[0] != len(texts):
            raise RuntimeError("Embedding API returned mismatched vector count.")
        return self._normalize(matrix)

    @staticmethod
    def _extract_vectors(data: dict) -> list[list[float]]:
        if isinstance(data.get("data"), list):
            items = data["data"]
            if items and isinstance(items[0], dict) and "embedding" in items[0]:
                return [item["embedding"] for item in items]
            if items and isinstance(items[0], list):
                return items

        if isinstance(data.get("embeddings"), list):
            return data["embeddings"]

        raise RuntimeError(f"Embedding API response has unexpected shape: {str(data)[:300]}")

    @staticmethod
    def _normalize(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms
