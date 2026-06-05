"""
RAG Pipeline Debugger — FastAPI Router

Provides a single POST endpoint that runs the full RAG pipeline
and returns every intermediate result for frontend visualization.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.container import container
from debug.debug_service import DebugPipelineService


debug_router = APIRouter(prefix="/debug", tags=["debug"])


class DebugPipelineRequest(BaseModel):
    question: str = Field(..., description="The question to ask the RAG system")
    file_name: str | None = Field(
        default=None,
        description="Optional PDF file name to restrict search scope",
    )
    parameters: dict | None = Field(
        default=None,
        description="Override pipeline parameters (chunk_size, top_k, etc.)",
    )


class DebugPipelineResponse(BaseModel):
    question: str
    file_name: str | None
    total_duration_seconds: float
    parameters: dict
    steps: dict


@debug_router.post("/pipeline", response_model=DebugPipelineResponse)
async def run_debug_pipeline(request: DebugPipelineRequest) -> DebugPipelineResponse:
    """
    Run the full RAG pipeline and return every intermediate result.

    Steps returned:
      - document: parsed document info
      - chunking: text chunks with previews
      - embedding: vector previews and all vectors
      - vector_search: vector search hits with scores
      - bm25_search: BM25 search hits with scores
      - hybrid_merge: merged hybrid results
      - reranking: reranked results
      - generation: LLM answer

    Parameters that can be overridden:
      - chunk_size (int)
      - chunk_overlap (int)
      - top_k (int)
      - vector_top_k (int)
      - bm25_top_k (int)
      - hybrid_candidate_pool (int)
      - vector_weight (float)
      - bm25_weight (float)
      - temperature (float)
    """
    try:
        service = DebugPipelineService(container)
        result = service.run_pipeline(
            question=request.question,
            file_name=request.file_name,
            parameters=request.parameters,
        )
        return DebugPipelineResponse(**result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc
