from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="RAG Prospectus QA API", alias="APP_NAME")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    data_root: str = Field(default="./data", alias="DATA_ROOT")
    raw_data_dir: str = Field(default="./data/raw", alias="RAW_DATA_DIR")
    processed_data_dir: str = Field(default="./data/processed", alias="PROCESSED_DATA_DIR")
    export_dir: str = Field(default="./data/exports", alias="EXPORT_DIR")
    default_file_name: str = Field(default="招股说明书1.pdf", alias="DEFAULT_FILE_NAME")

    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        alias="EMBEDDING_MODEL",
    )
    embedding_model_path: str = Field(default="", alias="EMBEDDING_MODEL_PATH")
    embedding_batch_size: int = Field(default=16, alias="EMBEDDING_BATCH_SIZE")
    chunk_size: int = Field(default=700, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, alias="CHUNK_OVERLAP")
    chunk_min_size: int = Field(default=180, alias="CHUNK_MIN_SIZE")
    top_k: int = Field(default=5, alias="TOP_K")
    vector_top_k: int = Field(default=8, alias="VECTOR_TOP_K")
    bm25_top_k: int = Field(default=8, alias="BM25_TOP_K")
    hybrid_top_k: int = Field(default=5, alias="HYBRID_TOP_K")
    hybrid_candidate_pool: int = Field(default=16, alias="HYBRID_CANDIDATE_POOL")
    reranker_candidate_pool: int = Field(default=8, alias="RERANKER_CANDIDATE_POOL")
    context_neighbor_window: int = Field(default=1, alias="CONTEXT_NEIGHBOR_WINDOW")
    bm25_weight: float = Field(default=0.4, alias="BM25_WEIGHT")
    vector_weight: float = Field(default=0.6, alias="VECTOR_WEIGHT")
    enable_reranker: bool = Field(default=True, alias="ENABLE_RERANKER")
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", alias="RERANKER_MODEL")
    reranker_top_k: int = Field(default=5, alias="RERANKER_TOP_K")

    milvus_uri: str = Field(default="http://127.0.0.1:19530", alias="MILVUS_URI")
    milvus_token: str = Field(default="", alias="MILVUS_TOKEN")
    milvus_collection: str = Field(default="prospectus_chunks", alias="MILVUS_COLLECTION")
    milvus_consistency: str = Field(default="Strong", alias="MILVUS_CONSISTENCY")

    redis_url: str = Field(default="redis://127.0.0.1:6379/0", alias="REDIS_URL")
    redis_cache_ttl: int = Field(default=3600, alias="REDIS_CACHE_TTL")
    redis_memory_ttl: int = Field(default=7200, alias="REDIS_MEMORY_TTL")
    conversation_history_limit: int = Field(default=6, alias="CONVERSATION_HISTORY_LIMIT")

    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")

    mysql_enabled: bool = Field(default=False, alias="MYSQL_ENABLED")
    mysql_host: str = Field(default="127.0.0.1", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="MYSQL_PASSWORD")
    mysql_database: str = Field(default="rag_ticket01", alias="MYSQL_DATABASE")

    eval_output_csv: str = Field(default="./data/exports/ragas_eval_results.csv", alias="EVAL_OUTPUT_CSV")
    eval_output_json: str = Field(default="./data/exports/ragas_eval_summary.json", alias="EVAL_OUTPUT_JSON")

    @property
    def raw_dir(self) -> Path:
        return Path(self.raw_data_dir).resolve()

    @property
    def processed_dir(self) -> Path:
        return Path(self.processed_data_dir).resolve()

    @property
    def exports_dir(self) -> Path:
        return Path(self.export_dir).resolve()

    @property
    def mysql_dsn(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )


settings = Settings()

for directory in [settings.raw_dir, settings.processed_dir, settings.exports_dir]:
    directory.mkdir(parents=True, exist_ok=True)
