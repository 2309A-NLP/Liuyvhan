import re
from collections import defaultdict
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

from app.core.config import settings


class BM25Service:
    def __init__(self) -> None:
        self.index_by_file: dict[str, dict] = {}

    def rebuild_index(self, file_name: str, chunks: list[dict]) -> None:
        # 人工智能 NLP-RAG-基于 PDF文档的问答系统: 为同一份文档构建本地 BM25 倒排索引，补足关键词召回能力。
        tokenized_corpus = [self._tokenize(chunk["content"]) for chunk in chunks]
        bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None
        self.index_by_file[file_name] = {
            "bm25": bm25,
            "chunks": chunks,
        }

    def restore_from_chunks_file(self, chunks_file: Path) -> bool:
        if not chunks_file.exists():
            return False

        try:
            import json

            chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
            if not chunks:
                return False
            file_name = chunks[0]["file_name"]
            self.rebuild_index(file_name=file_name, chunks=chunks)
            return True
        except Exception:
            return False

    def search(self, question: str, file_name: str | None, top_k: int | None = None) -> list[dict]:
        top_k = top_k or settings.bm25_top_k
        candidate_indexes = self._resolve_candidates(file_name)
        tokens = self._tokenize(question)
        if not tokens:
            return []

        results: list[dict] = []
        for resolved_file_name in candidate_indexes:
            entry = self.index_by_file.get(resolved_file_name)
            if not entry or entry["bm25"] is None:
                continue

            bm25 = entry["bm25"]
            chunks = entry["chunks"]
            raw_scores = bm25.get_scores(tokens)
            min_score = min(raw_scores) if len(raw_scores) > 0 else 0.0
            adjusted_scores = [float(score - min_score + 1e-6) for score in raw_scores]
            ranked = sorted(enumerate(adjusted_scores), key=lambda item: item[1], reverse=True)[:top_k]

            for chunk_index, score in ranked:
                chunk = dict(chunks[chunk_index])
                chunk["bm25_score"] = float(score)
                chunk["score"] = float(score)
                chunk["retrieval_type"] = "bm25"
                results.append(chunk)

        return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]

    def _resolve_candidates(self, file_name: str | None) -> list[str]:
        if file_name and file_name in self.index_by_file:
            return [file_name]
        return list(self.index_by_file.keys())

    def _tokenize(self, text: str) -> list[str]:
        normalized = text.lower().strip()
        if not normalized:
            return []

        english_tokens = re.findall(r"[a-z0-9_]+", normalized)
        chinese_text = "".join(char if "\u4e00" <= char <= "\u9fff" else " " for char in normalized)
        chinese_tokens = [token.strip() for token in jieba.cut_for_search(chinese_text) if token.strip()]
        merged_tokens = english_tokens + chinese_tokens

        token_counter = defaultdict(int)
        for token in merged_tokens:
            token_counter[token] += 1

        tokens: list[str] = []
        for token, count in token_counter.items():
            tokens.extend([token] * count)
        return tokens
