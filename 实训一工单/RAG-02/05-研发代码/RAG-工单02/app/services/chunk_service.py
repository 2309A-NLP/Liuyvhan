from app.core.config import settings


class ChunkService:
    def build_chunks(self, parsed_document: dict) -> list[dict]:
        chunks: list[dict] = []
        chunk_index = 0
        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap

        for page in parsed_document["pages"]:
            text = page["text"]
            if not text:
                continue

            start = 0
            while start < len(text):
                # 人工智能 NLP-RAG-基于 PDF文档的问答系统: 采用重叠切块，兼顾召回率与上下文连续性。
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
                            "content": content,
                            "content_length": len(content),
                        }
                    )
                    chunk_index += 1

                if end >= len(text):
                    break
                start = max(0, end - overlap)

        return chunks
