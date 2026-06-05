import re

from app.core.config import settings
from app.services.numeric_normalizer_service import NumericNormalizerService


class ChunkService:
    def __init__(self, numeric_normalizer_service: NumericNormalizerService | None = None) -> None:
        # 数值标准化服务：把 5,520.00 万元 / 5520万元 / 5,520万元 统一成可检索别名。
        self.numeric_normalizer_service = numeric_normalizer_service or NumericNormalizerService()

    def build_chunks(self, parsed_document: dict) -> list[dict]:
        chunks: list[dict] = []
        chunk_index = 0
        chunk_size = settings.chunk_size
        min_size = settings.chunk_min_size

        for page in parsed_document["pages"]:
            segments = page.get("segments") or [
                {
                    "type": "text",
                    "content": page.get("text", ""),
                    "section_title": page.get("section_title", ""),
                }
            ]
            buffer = ""
            buffer_type = "text"
            buffer_section_title = page.get("section_title", "")

            for segment in segments:
                segment_type = segment.get("type", "text")
                content = (segment.get("content") or "").strip()
                section_title = segment.get("section_title") or page.get("section_title", "")
                if not content:
                    continue

                if segment_type == "table":
                    if buffer.strip():
                        chunk_index = self._append_split_chunks(
                            chunks=chunks,
                            parsed_document=parsed_document,
                            page=page["page"],
                            content=buffer.strip(),
                            chunk_type=buffer_type,
                            section_title=buffer_section_title,
                            chunk_index=chunk_index,
                            chunk_size=chunk_size,
                            min_size=min_size,
                        )
                        buffer = ""

                    chunk_index = self._append_split_chunks(
                        chunks=chunks,
                        parsed_document=parsed_document,
                        page=page["page"],
                        content=content,
                        chunk_type="table",
                        section_title=section_title,
                        chunk_index=chunk_index,
                        chunk_size=chunk_size,
                        min_size=min_size,
                    )
                    continue

                candidate = f"{buffer}\n{content}".strip() if buffer else content
                if len(candidate) <= chunk_size:
                    buffer = candidate
                    buffer_type = "text"
                    buffer_section_title = section_title
                    continue

                if buffer.strip():
                    chunk_index = self._append_split_chunks(
                        chunks=chunks,
                        parsed_document=parsed_document,
                        page=page["page"],
                        content=buffer.strip(),
                        chunk_type=buffer_type,
                        section_title=buffer_section_title,
                        chunk_index=chunk_index,
                        chunk_size=chunk_size,
                        min_size=min_size,
                    )
                buffer = content
                buffer_type = "text"
                buffer_section_title = section_title

            if buffer.strip():
                chunk_index = self._append_split_chunks(
                    chunks=chunks,
                    parsed_document=parsed_document,
                    page=page["page"],
                    content=buffer.strip(),
                    chunk_type=buffer_type,
                    section_title=buffer_section_title,
                    chunk_index=chunk_index,
                    chunk_size=chunk_size,
                    min_size=min_size,
                )

        return chunks

    def _append_split_chunks(
        self,
        chunks: list[dict],
        parsed_document: dict,
        page: int,
        content: str,
        chunk_type: str,
        section_title: str,
        chunk_index: int,
        chunk_size: int,
        min_size: int,
    ) -> int:
        pieces = self._split_content(content=content, chunk_size=chunk_size, min_size=min_size, chunk_type=chunk_type)
        for piece in pieces:
            years = self._extract_years(piece)
            entities = self._extract_entities(piece)
            numeric_aliases = self.numeric_normalizer_service.extract_numeric_aliases(piece)
            is_financial_table = chunk_type == "table" and self._is_financial_table(piece)

            chunks.append(
                {
                    "chunk_id": f"{parsed_document['doc_id']}_{chunk_index}",
                    "doc_id": parsed_document["doc_id"],
                    "file_name": parsed_document["file_name"],
                    "page": page,
                    "chunk_index": chunk_index,
                    "chunk_type": chunk_type,
                    "section_title": section_title,
                    "years": years,
                    "entities": entities,
                    "numeric_aliases": numeric_aliases,
                    "is_financial_table": is_financial_table,
                    "search_text": self._build_search_text(
                        content=piece,
                        section_title=section_title,
                        years=years,
                        entities=entities,
                        numeric_aliases=numeric_aliases,
                    ),
                    "content": piece,
                    "content_length": len(piece),
                }
            )
            chunk_index += 1
        return chunk_index

    def _split_content(self, content: str, chunk_size: int, min_size: int, chunk_type: str) -> list[str]:
        normalized = content.strip()
        if not normalized:
            return []

        if len(normalized) <= chunk_size:
            return [normalized]

        separator = "\n" if chunk_type == "table" else "。"
        parts = [part.strip() for part in normalized.split(separator) if part.strip()]
        if separator == "。":
            parts = [f"{part}。" for part in parts]

        chunks: list[str] = []
        current = ""
        for part in parts:
            candidate = f"{current}\n{part}".strip() if current and chunk_type == "table" else f"{current}{part}".strip()
            if current and len(candidate) > chunk_size:
                chunks.append(current.strip())
                current = part
            else:
                current = candidate

        if current.strip():
            chunks.append(current.strip())

        if len(chunks) >= 2 and len(chunks[-1]) < min_size:
            joiner = "\n" if chunk_type == "table" else separator
            chunks[-2] = f"{chunks[-2]}{joiner}{chunks[-1]}".strip()
            chunks.pop()

        if any(len(item) > chunk_size for item in chunks):
            return self._split_by_window(normalized, chunk_size)
        return chunks

    def _split_by_window(self, content: str, chunk_size: int) -> list[str]:
        pieces: list[str] = []
        start = 0
        overlap = settings.chunk_overlap

        while start < len(content):
            end = min(start + chunk_size, len(content))
            piece = content[start:end].strip()
            if piece:
                pieces.append(piece)
            if end >= len(content):
                break
            start = max(0, end - overlap)

        return pieces

    def _extract_years(self, content: str) -> list[str]:
        matches = re.findall(r"(20\d{2}(?:年)?(?:1-6月)?)", content)
        return list(dict.fromkeys(matches))

    def _extract_entities(self, content: str) -> list[str]:
        patterns = [
            r"武汉兴图新科电子股份有限公司",
            r"程家明",
            r"某视频技术规范 ?1\.0",
            r"某情报、指挥、控制与通信网络一体化工程",
            r"国防军队",
            r"军队",
            r"政府机关",
            r"能源",
        ]
        entities: list[str] = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match not in entities:
                    entities.append(match)
        return entities

    def _is_financial_table(self, content: str) -> bool:
        signals = [
            "万元",
            "%",
            "募集资金",
            "收入",
            "金额",
            "注册资本",
            "补充流动资金",
        ]
        matched_count = sum(1 for signal in signals if signal in content)
        return matched_count >= 2

    def _build_search_text(
        self,
        content: str,
        section_title: str,
        years: list[str],
        entities: list[str],
        numeric_aliases: list[str],
    ) -> str:
        parts = [
            content,
            section_title,
            " ".join(years),
            " ".join(entities),
            " ".join(numeric_aliases),
        ]
        return " ".join(part.strip() for part in parts if part and part.strip())
