from app.core.config import settings


class ChunkService:
    def build_chunks(self, parsed_document: dict) -> list[dict]:
        chunks: list[dict] = []
        chunk_index = 0
        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap

        for page in parsed_document["pages"]:
            blocks = page.get("blocks") or [
                {
                    "block_type": "page_text",
                    "block_index": 0,
                    "content": page["text"],
                }
            ]

            for block in blocks:
                text = (block.get("content") or "").strip()
                if not text:
                    continue

                # 工单编号：人工智能 NLP-RAG-PDF 文档的表格解析及检索优化
                # 按页面块切分，优先保留表格块的结构，避免字段和数值被跨块截断。
                start = 0
                while start < len(text):
                    end = min(start + chunk_size, len(text))
                    content = text[start:end].strip()
                    if content:
                        chunks.append(
                            {
                                "chunk_id": f"{parsed_document['doc_id']}_{chunk_index}",
                                "doc_id": parsed_document["doc_id"],
                                "file_name": parsed_document["file_name"],
                                "page": page["page"],
                                "chunk_index": chunk_index,
                                "block_type": block.get("block_type", "page_text"),
                                "block_index": block.get("block_index", 0),
                                "content": content,
                                "content_length": len(content),
                            }
                        )
                        chunk_index += 1

                    if end >= len(text):
                        break
                    start = max(0, end - overlap)

        return chunks
