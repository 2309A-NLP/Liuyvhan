"""
RAG Pipeline Debug Service

Runs the full RAG pipeline step by step and returns every
intermediate result for visualization in the debug frontend.
Reuses all existing services from the project's container.
"""

import time
import json
from pathlib import Path


class DebugPipelineService:
    """Orchestrates the debug pipeline by calling each existing service sequentially."""

    def __init__(self, container):
        self.container = container
        self.settings = container.rag_service.settings

    def run_pipeline(self, question: str, file_name: str | None = None,
                     parameters: dict | None = None) -> dict:
        """Run the full pipeline and collect all intermediate results."""
        params = self._resolve_parameters(parameters)
        started = time.perf_counter()
        steps = {}

        # ── Step 1: Resolve document ──────────────────────────────────────
        doc_info = self._resolve_document(file_name)
        steps["document"] = doc_info

        # ── Step 2: Chunking ──────────────────────────────────────────────
        chunk_start = time.perf_counter()
        chunks = self.container.chunk_service.build_chunks(doc_info["parsed_document"])
        steps["chunking"] = {
            "duration_seconds": round(time.perf_counter() - chunk_start, 4),
            "total_chunks": len(chunks),
            "params": {"chunk_size": params["chunk_size"],
                       "chunk_overlap": params["chunk_overlap"]},
            "chunks": [
                {
                    "chunk_id": c["chunk_id"],
                    "page": c["page"],
                    "chunk_index": c["chunk_index"],
                    "content_length": c["content_length"],
                    "content_preview": c["content"][:200],
                }
                for c in chunks
            ],
        }

        # ── Step 3: Embedding ─────────────────────────────────────────────
        embed_start = time.perf_counter()
        texts = [c["content"] for c in chunks]
        full_vectors = self.container.embedding_service.embed_texts(texts) if texts else []
        steps["embedding"] = {
            "duration_seconds": round(time.perf_counter() - embed_start, 4),
            "dimension": self.container.embedding_service.embedding_dimension,
            "total_vectors": len(full_vectors),
            "vector_previews": [
                {"chunk_id": chunks[i]["chunk_id"],
                 "first_5_dims": vec[:5],
                 "norm": round(sum(v*v for v in vec)**0.5, 4)}
                for i, vec in enumerate(full_vectors)
            ],
            "all_vectors": full_vectors[:200],  # cap for frontend viz
        }

        # ── Step 3b: Query embedding ─────────────────────────────────────
        query_vector = self.container.embedding_service.embed_query(question)

        # ── Step 4: Vector Search ─────────────────────────────────────────
        vs_start = time.perf_counter()
        vector_hits = self._run_vector_search(question, query_vector, file_name, params)
        steps["vector_search"] = {
            "duration_seconds": round(time.perf_counter() - vs_start, 4),
            "total_hits": len(vector_hits),
            "params": {"top_k": params["vector_top_k"]},
            "hits": [
                {
                    "chunk_id": h["chunk_id"],
                    "score": round(float(h.get("score", 0)), 6),
                    "content_preview": h.get("content", "")[:200],
                    "page": h.get("page", 0),
                }
                for h in vector_hits
            ],
        }

        # ── Step 5: BM25 Search ──────────────────────────────────────────
        bm25_start = time.perf_counter()
        bm25_raw = self.container.bm25_service.search(
            question=question,
            file_name=file_name,
            top_k=params["bm25_top_k"],
        )
        steps["bm25_search"] = {
            "duration_seconds": round(time.perf_counter() - bm25_start, 4),
            "total_hits": len(bm25_raw),
            "params": {"top_k": params["bm25_top_k"]},
            "hits": [
                {
                    "chunk_id": h["chunk_id"],
                    "score": round(float(h.get("score", 0)), 6),
                    "content_preview": h.get("content", "")[:200],
                    "page": h.get("page", 0),
                }
                for h in bm25_raw
            ],
        }

        # ── Step 6: Hybrid Merge ─────────────────────────────────────────
        hybrid_start = time.perf_counter()
        hybrid_hits = self.container.rag_service._merge_hybrid_hits(
            vector_hits=vector_hits,
            bm25_hits=bm25_raw,
            top_k=params["hybrid_candidate_pool"],
        )
        steps["hybrid_merge"] = {
            "duration_seconds": round(time.perf_counter() - hybrid_start, 4),
            "total_hits": len(hybrid_hits),
            "params": {"vector_weight": params["vector_weight"],
                       "bm25_weight": params["bm25_weight"],
                       "pool_size": params["hybrid_candidate_pool"]},
            "hits": [
                {
                    "chunk_id": h["chunk_id"],
                    "hybrid_score": round(float(h.get("hybrid_score", h.get("score", 0))), 6),
                    "vector_score": round(float(h.get("vector_score", 0)), 6),
                    "bm25_score": round(float(h.get("bm25_score", 0)), 6),
                    "retrieval_type": h.get("retrieval_type", "unknown"),
                    "content_preview": h.get("content", "")[:200],
                }
                for h in hybrid_hits
            ],
        }

        # ── Step 7: Rerank ───────────────────────────────────────────────
        rerank_start = time.perf_counter()
        boosted_hits = self.container.rag_service._boost_structured_hits(
            question=question, hits=hybrid_hits,
            keywords=[],
        )
        reranked_hits = self.container.reranker_service.rerank(
            question=question,
            hits=boosted_hits,
            top_k=params["top_k"],
        )
        steps["reranking"] = {
            "duration_seconds": round(time.perf_counter() - rerank_start, 4),
            "total_hits": len(reranked_hits),
            "params": {"top_k": params["top_k"],
                       "reranker_enabled": self.container.reranker_service.enabled},
            "hits": [
                {
                    "chunk_id": h["chunk_id"],
                    "rerank_score": round(float(h.get("rerank_score", h.get("score", 0))), 6),
                    "score": round(float(h.get("score", 0)), 6),
                    "content": h.get("content", ""),
                    "page": h.get("page", 0),
                }
                for h in reranked_hits
            ],
        }

        # ── Step 8: LLM Generation ───────────────────────────────────────
        llm_start = time.perf_counter()
        answer = self.container.llm_service.answer_with_context(
            question, reranked_hits
        )
        steps["generation"] = {
            "duration_seconds": round(time.perf_counter() - llm_start, 4),
            "params": {"temperature": params["temperature"],
                       "model": getattr(self.settings, "llm_model", "default")},
            "answer": answer,
            "source_count": len(reranked_hits),
        }

        # ── Summary ──────────────────────────────────────────────────────
        total_duration = round(time.perf_counter() - started, 3)
        return {
            "question": question,
            "file_name": file_name,
            "total_duration_seconds": total_duration,
            "parameters": params,
            "steps": steps,
        }

    def _resolve_parameters(self, overrides: dict | None) -> dict:
        s = self.settings
        defaults = {
            "chunk_size": 700,
            "chunk_overlap": 120,
            "top_k": 5,
            "vector_top_k": 8,
            "bm25_top_k": 8,
            "hybrid_candidate_pool": 16,
            "vector_weight": 0.6,
            "bm25_weight": 0.4,
            "temperature": 0.7,
        }
        for key in defaults:
            val = getattr(s, key, None)
            if val is not None:
                defaults[key] = val

        if overrides:
            for key, val in overrides.items():
                if key in defaults and val is not None:
                    defaults[key] = val

        return defaults

    def _resolve_document(self, file_name: str | None) -> dict:
        if not file_name:
            file_name = self.settings.default_file_name
        file_path = self.container.rag_service.resolve_file_path(file_name)
        parsed_document = self.container.pdf_service.parse_pdf(file_path)
        return {
            "file_name": file_name,
            "file_path": str(file_path),
            "parsed_document": parsed_document,
            "page_count": parsed_document.get("page_count", 0),
        }

    def _run_vector_search(self, question: str, query_vector: list[float],
                           file_name: str | None, params: dict) -> list[dict]:
        """Run vector search using the existing vector store."""
        filter_key = "file_name"
        filter_val = file_name or self.settings.default_file_name

        raw_hits = self.container.vector_store.search(
            query_vector=query_vector,
            file_name=filter_val,
            top_k=max(params["top_k"], params["vector_top_k"] * 2),
        )

        # Enrich hits with chunk content from saved chunks files
        doc_id = self._find_doc_id(file_name)
        enriched = []
        for hit in raw_hits:
            h = dict(hit)
            h["doc_id"] = doc_id
            enriched.append(h)
        return enriched

    def _find_doc_id(self, file_name: str | None) -> str:
        """Find doc_id for a given file_name from manifest files."""
        import json as _json
        if not file_name:
            return ""
        manifests = sorted(Path(self.settings.processed_dir).glob("*_manifest.json"))
        for mf in manifests:
            try:
                data = _json.loads(mf.read_text(encoding="utf-8"))
                if data.get("file_name") == file_name:
                    return data.get("doc_id", "")
            except Exception:
                continue
        return ""
