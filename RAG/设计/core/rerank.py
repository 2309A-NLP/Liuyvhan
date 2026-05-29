from __future__ import annotations

import re

import requests

"""两种模式
1. 远程 rerank API  
在 Milvus 混合检索已经召回一批候选文档之后，再做一次更精细的相关性判断，把最适合当前问题的文档排到前面
2. 本地 heuristic fallback"""
class RerankService:
    """Rerank service with remote-API support and local heuristic fallback."""

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.remote_url = settings.rerank_api_url.strip()
        self.backend = "remote_api" if self.remote_url else settings.rerank_backend
        self.logger.info(
            "Rerank backend=%s, configured_model=%s, remote_enabled=%s",
            self.backend,
            settings.rerank_model_name,
            bool(self.remote_url),
        )

    def rerank(self, query: str, candidates: list[dict], top_n: int) -> list[dict]:
        if not candidates:
            return []

        if self.remote_url:
            try:
                return self._rerank_remote(query=query, candidates=candidates, top_n=top_n)
            except Exception as exc:
                self.logger.warning(
                    "Remote rerank failed, fallback to local heuristic. error=%s",
                    exc,
                )

        return self._rerank_local(query=query, candidates=candidates, top_n=top_n)

    def _rerank_remote(self, query: str, candidates: list[dict], top_n: int) -> list[dict]:
        headers = {"Content-Type": "application/json"}
        if self.settings.rerank_api_key:
            headers["Authorization"] = f"Bearer {self.settings.rerank_api_key}"

        documents = [self._join_doc_text(item) for item in candidates]
        # 把候选文档整理成 rerank 模型能看的文本 意思是把每条候选文档变成一段纯文本
        # 所以这时候传给重排序模型的不是字典，不是向量，而是：
        # 一个问题 query
        # 一组候选文档文本 documents

        payload = {
            "model": self.settings.rerank_model_name,
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        # 把每个候选文档拼成文本
        # 通常是：
        # title + content
        # 把用户问题 query 和候选文档列表一起发给 rerank 模型
        # 模型返回每个候选的相关性分数



        endpoint = self.remote_url.rstrip("/")
        self.logger.info(
            "Calling rerank service model=%s endpoint=%s candidates=%s",
            self.settings.rerank_model_name,
            endpoint,
            len(candidates),
        )
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=self.settings.rerank_api_timeout,
        )
        response.raise_for_status()
        data = response.json()
        scored_items = self._extract_rerank_scores(data)

        reranked: list[dict] = []
        for item in scored_items:
            index = int(item["index"])
            if index < 0 or index >= len(candidates):
                continue
            candidate = dict(candidates[index])
            candidate["rerank_score"] = round(float(item["score"]), 4)
            # 远程 rerank 最终会给每个候选文档补一个：
            # rerank_score  然后再按这个分数排序。
            reranked.append(candidate)
            # 取出 rerank 返回的 index
            # 用这个 index 去原始 candidates 里找到对应文档
            # 给这条文档加上 rerank_score
            # 放进新的排序结果里

        """按返回的rerank-score 排序 返回前top_n"""
        reranked.sort(key=lambda row: row["rerank_score"], reverse=True)
        return reranked[:top_n]

    def _rerank_local(self, query: str, candidates: list[dict], top_n: int) -> list[dict]:
        query_terms = self._tokenize(query)
        query_term_set = set(query_terms)
        query_phrases = self._extract_phrases(query)
        rescored: list[dict] = []

        for item in candidates:
            candidate = dict(item)
            title_terms = set(self._tokenize(candidate.get("title", "")))
            content_terms = set(self._tokenize(candidate["content"]))
            combined_text = self._join_doc_text(candidate).lower()


            lexical_overlap = len(query_term_set & content_terms) / max(len(query_term_set), 1)
            title_overlap = len(query_term_set & title_terms) / max(len(query_term_set), 1)
            phrase_overlap = sum(1 for phrase in query_phrases if phrase in combined_text) / max(len(query_phrases), 1)

            candidate["rerank_score"] = round(
                0.55 * float(candidate.get("score", 0.0))
                + 0.25 * lexical_overlap
                + 0.1 * title_overlap
                + 0.1 * phrase_overlap,
                4,
            )
            rescored.append(candidate)

        rescored.sort(key=lambda row: row["rerank_score"], reverse=True)
        return rescored[:top_n]

    @staticmethod
    def _extract_rerank_scores(data: dict) -> list[dict]:
        if isinstance(data.get("results"), list):
            results = data["results"]
            extracted = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                index = item.get("index")
                score = item.get("relevance_score", item.get("score"))
                if index is None or score is None:
                    continue
                extracted.append({"index": index, "score": score})
            if extracted:
                return extracted

        if isinstance(data.get("data"), list):
            results = data["data"]
            extracted = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                index = item.get("index")
                score = item.get("relevance_score", item.get("score"))
                if index is None or score is None:
                    continue
                extracted.append({"index": index, "score": score})
            if extracted:
                return extracted

        raise RuntimeError(f"Rerank API response has unexpected shape: {str(data)[:300]}")

    @staticmethod
    def _join_doc_text(item: dict) -> str:
        return f"{item.get('title', '')} {item.get('content', '')}".strip()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
        words = [word for word in cleaned.split() if word]
        dense = "".join(words)
        ngrams = [dense[i : i + 2] for i in range(max(1, len(dense) - 1))] if dense else []
        tokens = words + ngrams
        return tokens or [text[i : i + 2] for i in range(max(1, len(text) - 1))]

    @staticmethod
    def _extract_phrases(text: str) -> list[str]:
        phrases = [part.strip().lower() for part in re.split(r"[，,。！？!?；;\s]+", text) if part.strip()]
        return [phrase for phrase in phrases if len(phrase) >= 4]
