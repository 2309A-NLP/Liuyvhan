from typing import Any

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    file_name: str
    file_path: str
    size_bytes: int


class IndexRequest(BaseModel):
    file_name: str = Field(default="招股说明书1.pdf")
    rebuild: bool = Field(default=False)


class IndexResponse(BaseModel):
    doc_id: str
    file_name: str
    pages: int
    chunks: int
    duration_seconds: float
    manifest_path: str


class SourceItem(BaseModel):
    chunk_id: str
    file_name: str
    page: int
    score: float
    content: str
    block_type: str | None = None
    image_path: str | None = None
    retrieval_type: str | None = None
    vector_score: float | None = None
    bm25_score: float | None = None
    hybrid_score: float | None = None
    rerank_score: float | None = None


class AskRequest(BaseModel):
    question: str
    file_name: str | None = None
    top_k: int | None = None
    force_refresh: bool = False
    conversation_id: str | None = None


class AskResponse(BaseModel):
    mode: str
    question: str
    answer: str
    sources: list[SourceItem]
    latency_seconds: float
    cached: bool = False
    conversation_id: str | None = None
    query_understanding: dict | None = None


class FeedbackRequest(BaseModel):
    request_mode: str
    question: str
    answer: str
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class FeedbackResponse(BaseModel):
    status: str
    storage: str


class EvaluationQuestion(BaseModel):
    id: int
    question: str
    reference_answer: str


class EvaluationRunRequest(BaseModel):
    file_name: str | None = None
    top_k: int | None = None
    questions_file: str = "./data/processed/evaluation_questions.json"


class EvaluationRow(BaseModel):
    id: int
    question: str
    reference_answer: str
    rag_answer: str
    llm_answer: str
    rag_sources: list[dict[str, Any]]


class EvaluationSummary(BaseModel):
    total_questions: int
    ragas_metrics: dict[str, float]
    csv_path: str
    json_path: str


class IndexAllRequest(BaseModel):
    rebuild: bool = Field(default=True)


class BatchIndexItem(BaseModel):
    file_name: str
    status: str  # "success" | "failed"
    doc_id: str | None = None
    pages: int | None = None
    chunks: int | None = None
    duration_seconds: float | None = None
    error: str | None = None


class BatchIndexResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[BatchIndexItem]
    total_duration_seconds: float


class DocumentStatus(BaseModel):
    indexed_documents: list[dict[str, Any]]
