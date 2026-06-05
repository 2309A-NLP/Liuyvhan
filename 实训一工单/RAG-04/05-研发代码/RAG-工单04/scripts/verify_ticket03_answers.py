import json
from pathlib import Path

from app.services.bm25_service import BM25Service
from app.services.cache_service import CacheService
from app.services.chunk_service import ChunkService
from app.services.pdf_service import PDFService
from app.services.query_enhancer_service import QueryEnhancerService
from app.services.rag_service import RAGService


class LocalOnlyVectorStore:
    def delete_document(self, doc_id: str) -> None:
        return None

    def upsert_chunks(self, doc_id: str, chunks: list[dict], embeddings: list[list[float]]) -> None:
        return None

    def search(self, query_vector: list[float], file_name: str | None, top_k: int) -> list[dict]:
        return []

    def write_manifest(self, manifest: dict, output_path: Path) -> None:
        output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_documents(self) -> list[dict]:
        return []


class LocalEmbeddingService:
    embedding_dimension = 8

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.embedding_dimension for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0] * self.embedding_dimension


class LocalRerankerService:
    def rerank(self, question: str, hits: list[dict], top_k: int | None = None) -> list[dict]:
        return hits[: top_k or len(hits)]


class LocalLLMService:
    def answer_with_context(self, question: str, contexts: list[dict]) -> str:
        raise RuntimeError("Skip remote LLM in local verification")

    def answer_directly(self, question: str) -> str:
        return "Skip remote LLM in local verification"


def build_service() -> RAGService:
    pdf_service = PDFService()
    chunk_service = ChunkService()
    bm25_service = BM25Service()
    embedding_service = LocalEmbeddingService()
    query_enhancer_service = QueryEnhancerService()
    reranker_service = LocalRerankerService()
    vector_store = LocalOnlyVectorStore()
    cache_service = CacheService()
    llm_service = LocalLLMService()
    return RAGService(
        pdf_service=pdf_service,
        chunk_service=chunk_service,
        bm25_service=bm25_service,
        embedding_service=embedding_service,
        query_enhancer_service=query_enhancer_service,
        reranker_service=reranker_service,
        vector_store=vector_store,
        cache_service=cache_service,
        llm_service=llm_service,
    )


def main() -> None:
    rag_service = build_service()
    questions = json.loads(Path("data/processed/evaluation_questions.json").read_text(encoding="utf-8"))

    for item in questions:
        result = rag_service.ask_rag(item["question"], force_refresh=True, top_k=5)
        pages = sorted({source["page"] for source in result["sources"]})
        print(f"[{item['id']}] {item['question']}")
        print("ANSWER:", result["answer"])
        print("PAGES:", pages)
        print("LATENCY:", result["latency_seconds"])
        print()


if __name__ == "__main__":
    main()
