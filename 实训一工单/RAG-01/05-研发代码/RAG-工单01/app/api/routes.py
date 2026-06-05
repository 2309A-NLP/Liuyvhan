from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import settings
from app.core.container import container
from app.models.schemas import (
    AskRequest,
    AskResponse,
    DocumentStatus,
    EvaluationRunRequest,
    EvaluationSummary,
    FeedbackRequest,
    FeedbackResponse,
    IndexRequest,
    IndexResponse,
    UploadResponse,
)


router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    file_bytes = await file.read()
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件上传。")

    file_path = container.pdf_service.save_upload(file_bytes, file.filename, settings.raw_dir)
    return UploadResponse(file_name=file.filename, file_path=str(file_path), size_bytes=len(file_bytes))


@router.post("/documents/index", response_model=IndexResponse)
async def build_index(request: IndexRequest) -> IndexResponse:
    try:
        file_path = container.rag_service.resolve_file_path(request.file_name)
        result = container.rag_service.ingest_file(file_path=file_path, rebuild=request.rebuild)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return IndexResponse(**result)


@router.get("/documents/status", response_model=DocumentStatus)
async def document_status() -> DocumentStatus:
    return DocumentStatus(indexed_documents=container.rag_service.list_documents())


@router.post("/chat/rag", response_model=AskResponse)
async def ask_rag(request: AskRequest) -> AskResponse:
    try:
        result = container.rag_service.ask_rag(
            question=request.question,
            file_name=request.file_name,
            top_k=request.top_k,
            session_id=request.session_id,
            clear_history=request.clear_history,
            force_refresh=request.force_refresh,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AskResponse(**result)


@router.post("/chat/llm", response_model=AskResponse)
async def ask_llm(request: AskRequest) -> AskResponse:
    try:
        result = container.rag_service.ask_llm(
            question=request.question,
            session_id=request.session_id,
            clear_history=request.clear_history,
            force_refresh=request.force_refresh,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AskResponse(**result)


@router.post("/feedback", response_model=FeedbackResponse)
async def save_feedback(request: FeedbackRequest) -> FeedbackResponse:
    storage = container.feedback_service.save_feedback(request.model_dump())
    return FeedbackResponse(status="success", storage=storage)


@router.post("/evaluation/run", response_model=EvaluationSummary)
async def run_evaluation(request: EvaluationRunRequest) -> EvaluationSummary:
    try:
        result = container.evaluation_service.run(
            questions_file=request.questions_file,
            file_name=request.file_name,
            top_k=request.top_k,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return EvaluationSummary(
        total_questions=result["total_questions"],
        ragas_metrics=result["ragas_metrics"],
        csv_path=result["csv_path"],
        json_path=result["json_path"],
    )
