import json
import time
from pathlib import Path

from pymilvus import DataType, MilvusClient

from app.core.config import settings


class MilvusVectorStore:
    def __init__(self, embedding_dimension: int) -> None:
        self.embedding_dimension = embedding_dimension
        self.client = MilvusClient(uri=settings.milvus_uri, token=settings.milvus_token or None)
        self.collection_name = settings.milvus_collection
        self._collection_loaded = False
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if self.client.has_collection(collection_name=self.collection_name):
            current_dim = self._get_collection_embedding_dim()
            if current_dim == self.embedding_dimension and self._collection_is_ready() and self._collection_schema_matches():
                self._load_collection()
                return
            self.client.drop_collection(collection_name=self.collection_name)
            self._collection_loaded = False

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(field_name="chunk_id", datatype=DataType.VARCHAR, is_primary=True, max_length=128)
        schema.add_field(field_name="doc_id", datatype=DataType.VARCHAR, max_length=64)
        schema.add_field(field_name="file_name", datatype=DataType.VARCHAR, max_length=255)
        schema.add_field(field_name="page", datatype=DataType.INT64)
        schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="content_length", datatype=DataType.INT64)
        schema.add_field(field_name="chunk_type", datatype=DataType.VARCHAR, max_length=32)
        schema.add_field(field_name="section_title", datatype=DataType.VARCHAR, max_length=255)
        schema.add_field(field_name="years", datatype=DataType.VARCHAR, max_length=255)
        schema.add_field(field_name="entities", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="numeric_aliases", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="is_financial_table", datatype=DataType.BOOL)
        schema.add_field(field_name="search_text", datatype=DataType.VARCHAR, max_length=65535)
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

    def upsert_chunks(self, doc_id: str, chunks: list[dict], embeddings: list[list[float]]) -> None:
        self._load_collection()
        self.delete_document(doc_id)
        payload = []
        for chunk, embedding in zip(chunks, embeddings):
            record = dict(chunk)
            record["chunk_type"] = record.get("chunk_type", "text")
            record["section_title"] = record.get("section_title", "")[:255]
            record["years"] = json.dumps(record.get("years", []), ensure_ascii=False)
            record["entities"] = json.dumps(record.get("entities", []), ensure_ascii=False)
            record["numeric_aliases"] = json.dumps(record.get("numeric_aliases", []), ensure_ascii=False)
            record["is_financial_table"] = bool(record.get("is_financial_table", False))
            record["search_text"] = record.get("search_text", record.get("content", ""))[:65535]
            record["embedding"] = embedding
            payload.append(record)
        if payload:
            self.client.insert(collection_name=self.collection_name, data=payload)

    def delete_document(self, doc_id: str) -> None:
        if not self.client.has_collection(collection_name=self.collection_name):
            return
        self._load_collection()
        self.client.delete(collection_name=self.collection_name, filter=f'doc_id == "{doc_id}"')

    def search(self, query_vector: list[float], file_name: str | None, top_k: int) -> list[dict]:
        filter_expression = f'file_name == "{file_name}"' if file_name else ""
        self._load_collection()
        results = self.client.search(
            collection_name=self.collection_name,
            data=[query_vector],
            anns_field="embedding",
            filter=filter_expression,
            limit=top_k,
            output_fields=[
                "chunk_id",
                "doc_id",
                "file_name",
                "page",
                "chunk_index",
                "content",
                "chunk_type",
                "section_title",
                "years",
                "entities",
                "numeric_aliases",
                "is_financial_table",
                "search_text",
            ],
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
                    "chunk_type": entity.get("chunk_type", "text"),
                    "section_title": entity.get("section_title", ""),
                    "years": self._safe_load_json_array(entity.get("years")),
                    "entities": self._safe_load_json_array(entity.get("entities")),
                    "numeric_aliases": self._safe_load_json_array(entity.get("numeric_aliases")),
                    "is_financial_table": bool(entity.get("is_financial_table", False)),
                    "search_text": entity.get("search_text", entity.get("content", "")),
                    "score": float(item["distance"]),
                }
            )
        return flattened

    def write_manifest(self, manifest: dict, output_path: Path) -> None:
        output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_documents(self) -> list[dict]:
        documents = []
        for manifest_file in sorted(settings.processed_dir.glob("*_manifest.json")):
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            documents.append(data)
        return documents

    def _load_collection(self) -> None:
        if self._collection_loaded:
            return
        try:
            self.client.load_collection(collection_name=self.collection_name)
            for _ in range(20):
                state = self.client.get_load_state(collection_name=self.collection_name)
                state_name = str(state.get("state", "")).lower()
                if "loaded" in state_name:
                    self._collection_loaded = True
                    return
                time.sleep(0.2)
        except Exception:
            return

    def _collection_is_ready(self) -> bool:
        try:
            indexes = self.client.list_indexes(collection_name=self.collection_name)
            if not indexes:
                return False
            index_names = {str(item.get("field_name", "")) for item in indexes if isinstance(item, dict)}
            return "embedding" in index_names or len(indexes) > 0
        except Exception:
            return False

    def _collection_schema_matches(self) -> bool:
        try:
            description = self.client.describe_collection(collection_name=self.collection_name)
            fields = {field.get("name") for field in description.get("fields", [])}
            required_fields = {
                "chunk_id",
                "doc_id",
                "file_name",
                "page",
                "chunk_index",
                "content",
                "content_length",
                "chunk_type",
                "section_title",
                "years",
                "entities",
                "numeric_aliases",
                "is_financial_table",
                "search_text",
                "embedding",
            }
            return required_fields.issubset(fields)
        except Exception:
            return False

    def _get_collection_embedding_dim(self) -> int | None:
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

    def _safe_load_json_array(self, value: str | None) -> list[str]:
        if not value:
            return []
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
