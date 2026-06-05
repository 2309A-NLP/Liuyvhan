import json
import time
from pathlib import Path

from pymilvus import DataType, MilvusClient

from app.core.config import settings


class MilvusVectorStore:
    EXPECTED_VARCHAR_FIELDS = {
        "chunk_id": 128,
        "doc_id": 64,
        "file_name": 255,
        "content": 65535,
    }

    def __init__(self, embedding_dimension: int) -> None:
        self.embedding_dimension = embedding_dimension
        self.collection_name = settings.milvus_collection
        self.client = None
        self.available = False

        try:
            self.client = MilvusClient(uri=settings.milvus_uri, token=settings.milvus_token or None)
            self._ensure_collection()
            self.available = True
        except Exception:
            self.client = None
            self.available = False

    def _ensure_collection(self) -> None:
        if self.client is None:
            return

        if self.client.has_collection(collection_name=self.collection_name):
            if self._collection_matches_expected_schema() and self._collection_is_ready():
                return
            self.client.drop_collection(collection_name=self.collection_name)

        # 工单编号：人工智能 NLP-RAG-PDF 文档的表格解析及检索优化
        # 根据当前嵌入维度自动重建 collection，避免模型调整后的维度冲突。
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="chunk_id", datatype=DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="file_name", datatype=DataType.VARCHAR, max_length=255)
        schema.add_field(field_name="page", datatype=DataType.INT64)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="content_length", datatype=DataType.INT64)
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=self.embedding_dimension)

        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE")

        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
            consistency_level=settings.milvus_consistency,
        )
        self._load_collection()

    def _collection_matches_expected_schema(self) -> bool:
        if self.client is None:
            return False

        try:
            description = self.client.describe_collection(collection_name=self.collection_name)
        except Exception:
            return False

        fields = description.get("fields", [])
        field_map = {field.get("name"): field for field in fields}
        expected_names = {
            "chunk_id",
            "doc_id",
            "file_name",
            "page",
            "chunk_index",
            "content",
            "content_length",
            "embedding",
        }
        actual_names = set(field_map.keys())

        if actual_names != expected_names:
            return False

        if self._get_collection_embedding_dim() != self.embedding_dimension:
            return False

        for field_name, max_length in self.EXPECTED_VARCHAR_FIELDS.items():
            field = field_map.get(field_name, {})
            params = field.get("params", {})
            if int(params.get("max_length", -1)) != max_length:
                return False

        return True

    def upsert_chunks(self, doc_id: str, chunks: list[dict], embeddings: list[list[float]]) -> None:
        if not self.available or self.client is None:
            return

        self._load_collection()
        self.delete_document(doc_id)
        payload = []
        for chunk, embedding in zip(chunks, embeddings):
            record = {
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "file_name": chunk["file_name"],
                "page": chunk["page"],
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"],
                "content_length": chunk["content_length"],
                "embedding": embedding,
            }
            payload.append(record)
        if payload:
            self.client.insert(collection_name=self.collection_name, data=payload)

    def delete_document(self, doc_id: str) -> None:
        if not self.available or self.client is None:
            return
        if not self.client.has_collection(collection_name=self.collection_name):
            return
        self._load_collection()
        self.client.delete(collection_name=self.collection_name, filter=f'doc_id == "{doc_id}"')

    def search(self, query_vector: list[float], file_name: str | None, top_k: int) -> list[dict]:
        if not self.available or self.client is None:
            return []

        filter_expression = ""
        if file_name:
            filter_expression = f'file_name == "{file_name}"'

        self._load_collection()
        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            anns_field="embedding",
            filter=filter_expression,
            limit=top_k,
            output_fields=["chunk_id", "doc_id", "file_name", "page", "chunk_index", "content"],
            search_params={"metric_type": "COSINE", "params": {}},
        )

        flattened: list[dict] = []
        for item in results[0]:
            entity = item["entity"]
            flattened.append(
                {
                    "chunk_id": entity["chunk_id"],
                    "doc_id": entity["doc_id"],
                    "file_name": entity["file_name"],
                    "page": entity["page"],
                    "chunk_index": entity["chunk_index"],
                    "content": entity["content"],
                    "score": float(item["distance"]),
                }
            )
        return flattened

    def write_manifest(self, manifest: dict, output_path: Path) -> None:
        output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_documents(self) -> list[dict]:
        manifest_files = sorted(settings.processed_dir.glob("*_manifest.json"))
        documents = []
        for manifest_file in manifest_files:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            documents.append(data)
        return documents

    def _load_collection(self) -> None:
        if not self.available or self.client is None:
            return
        try:
            self.client.load_collection(collection_name=self.collection_name)
            for _ in range(20):
                state = self.client.get_load_state(collection_name=self.collection_name)
                state_name = str(state.get("state", "")).lower()
                if "loaded" in state_name:
                    return
                time.sleep(0.2)
        except Exception:
            return

    def _collection_is_ready(self) -> bool:
        if self.client is None:
            return False
        try:
            indexes = self.client.list_indexes(collection_name=self.collection_name)
            if not indexes:
                return False
            index_names = {str(item.get("field_name", "")) for item in indexes if isinstance(item, dict)}
            return "embedding" in index_names or len(indexes) > 0
        except Exception:
            return False

    def _get_collection_embedding_dim(self) -> int | None:
        if self.client is None:
            return None
        try:
            description = self.client.describe_collection(collection_name=self.collection_name)
            for field in description.get("fields", []):
                if field.get("name") == "embedding":
                    params = field.get("params", {})
                    dim = params.get("dim")
                    return int(dim) if dim is not None else None
        except Exception:
            return None
        return None
