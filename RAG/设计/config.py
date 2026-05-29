# 配置文件（包含所有配置）
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "RAG Roleplay System")
    app_version: str = "1.0.0"
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8000"))

    db_backend: str = os.getenv("DB_BACKEND", "sqlite")
    sqlite_path: Path = BASE_DIR / "data" / "storage" / "app.db"
    mysql_host: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "")
    mysql_charset: str = os.getenv("MYSQL_CHARSET", "utf8mb4")

    redis_enabled: bool = _env_bool("REDIS_ENABLED", False)
    redis_host: str = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))

    milvus_enabled: bool = _env_bool("MILVUS_ENABLED", False)
    milvus_uri: str = os.getenv("MILVUS_URI", "http://127.0.0.1:19530")
    milvus_token: str = os.getenv("MILVUS_TOKEN", "")

    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "hashing")
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    embedding_dimension: int = int(os.getenv("EMBEDDING_DIMENSION", "512"))
    embedding_api_url: str = os.getenv("EMBEDDING_API_URL", "")
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "")
    embedding_api_timeout: int = int(os.getenv("EMBEDDING_API_TIMEOUT", "30"))
    local_embedding_model_path: str = os.getenv("LOCAL_EMBEDDING_MODEL_PATH", "")
    local_embedding_service_host: str = os.getenv("LOCAL_EMBEDDING_SERVICE_HOST", "127.0.0.1")
    local_embedding_service_port: int = int(os.getenv("LOCAL_EMBEDDING_SERVICE_PORT", "8002"))
    use_bge_models: bool = _env_bool("USE_BGE_MODELS", False)

    rerank_backend: str = os.getenv("RERANK_BACKEND", "heuristic")
    rerank_model_name: str = os.getenv("RERANK_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
    rerank_api_url: str = os.getenv("RERANK_API_URL", "")
    rerank_api_key: str = os.getenv("RERANK_API_KEY", "")
    rerank_api_timeout: int = int(os.getenv("RERANK_API_TIMEOUT", "30"))
    local_rerank_model_path: str = os.getenv("LOCAL_RERANK_MODEL_PATH", "")
    local_rerank_service_host: str = os.getenv("LOCAL_RERANK_SERVICE_HOST", "127.0.0.1")
    local_rerank_service_port: int = int(os.getenv("LOCAL_RERANK_SERVICE_PORT", "8003"))

    llm_provider: str = os.getenv("LLM_PROVIDER", "siliconflow")
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
    llm_api_base: str = os.getenv("LLM_API_BASE", "https://api.siliconflow.cn/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_timeout: int = int(os.getenv("LLM_TIMEOUT", "30"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.35"))
    llm_top_p: float = float(os.getenv("LLM_TOP_P", "0.9"))
    llm_presence_penalty: float = float(os.getenv("LLM_PRESENCE_PENALTY", "0.2"))

    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "6"))
    rerank_top_n: int = int(os.getenv("RERANK_TOP_N", "4"))
    retrieval_query_variants: int = int(os.getenv("RETRIEVAL_QUERY_VARIANTS", "3"))
    retrieval_min_score: float = float(os.getenv("RETRIEVAL_MIN_SCORE", "0.18"))
    short_memory_turns: int = int(os.getenv("SHORT_MEMORY_TURNS", "6"))
    long_memory_top_k: int = int(os.getenv("LONG_MEMORY_TOP_K", "2"))

    knowledge_collection: str = "role_knowledge"
    long_memory_collection: str = "user_long_memory"
    demo_seed_version: str = "2026-04-28-ui-refresh"
    pdf_auto_import_enabled: bool = _env_bool("PDF_AUTO_IMPORT_ENABLED", True)
    pdf_auto_import_default_role_id: str = os.getenv("PDF_AUTO_IMPORT_DEFAULT_ROLE_ID", "doctor")
    pdf_parser_backend: str = os.getenv("PDF_PARSER_BACKEND", "pymupdf")
    mineru_api_url: str = os.getenv("MINERU_API_URL", "")
    mineru_api_token: str = os.getenv("MINERU_API_TOKEN", "")
    mineru_backend: str = os.getenv("MINERU_BACKEND", "hybrid-auto-engine")
    mineru_parse_method: str = os.getenv("MINERU_PARSE_METHOD", "auto")
    mineru_language: str = os.getenv("MINERU_LANGUAGE", "ch")
    mineru_formula_enable: bool = _env_bool("MINERU_FORMULA_ENABLE", True)
    mineru_table_enable: bool = _env_bool("MINERU_TABLE_ENABLE", True)
    mineru_image_analysis: bool = _env_bool("MINERU_IMAGE_ANALYSIS", True)
    mineru_timeout: int = int(os.getenv("MINERU_TIMEOUT", "300"))
    mineru_start_page_id: int = int(os.getenv("MINERU_START_PAGE_ID", "0"))
    mineru_end_page_id: int | None = (
        int(os.getenv("MINERU_END_PAGE_ID")) if os.getenv("MINERU_END_PAGE_ID") not in (None, "") else None
    )

    roles_seed_path: Path = BASE_DIR / "data" / "seed" / "roles.json"
    knowledge_seed_path: Path = BASE_DIR / "data" / "seed" / "knowledge_documents.json"
    eval_seed_path: Path = BASE_DIR / "data" / "seed" / "eval_dataset.json"
    raw_pdf_dir: Path = BASE_DIR / "data" / "raw_pdfs"
    pdf_preview_dir: Path = BASE_DIR / "data" / "pdf_preview"
    pdf_images_dir: Path = BASE_DIR / "data" / "pdf_images"
    local_milvus_path: Path = BASE_DIR / "data" / "storage" / "milvus_store.json"
    local_redis_path: Path = BASE_DIR / "data" / "storage" / "redis_store.json"
    pdf_import_state_path: Path = BASE_DIR / "data" / "storage" / "pdf_import_state.json"
    demo_seed_version_path: Path = BASE_DIR / "data" / "storage" / "demo_seed_version.txt"
    log_path: Path = BASE_DIR / "logs" / "app.log"

    def ensure_directories(self) -> None:
        for path in (
            self.sqlite_path.parent,
            self.local_milvus_path.parent,
            self.local_redis_path.parent,
            self.log_path.parent,
            self.roles_seed_path.parent,
            self.raw_pdf_dir,
            self.pdf_preview_dir,
            self.pdf_images_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


SETTINGS = Settings()
SETTINGS.ensure_directories()
