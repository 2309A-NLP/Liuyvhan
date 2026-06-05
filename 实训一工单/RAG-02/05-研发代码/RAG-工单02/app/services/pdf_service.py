import hashlib
from pathlib import Path

import pdfplumber


class PDFService:
    def save_upload(self, file_bytes: bytes, file_name: str, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / file_name
        file_path.write_bytes(file_bytes)
        return file_path

    def parse_pdf(self, file_path: Path) -> dict:
        pages: list[dict] = []
        with pdfplumber.open(file_path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                # 人工智能 NLP-RAG-基于 PDF文档的问答系统: 同时提取正文和表格，减少招股书关键信息遗漏。
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                tables = page.extract_tables() or []
                table_texts = [self._table_to_markdown(table) for table in tables if table]
                merged_text = "\n\n".join([value for value in [page_text, *table_texts] if value.strip()])
                pages.append(
                    {
                        "page": page_index,
                        "text": merged_text.strip(),
                        "raw_text": page_text.strip(),
                        "tables": table_texts,
                    }
                )

        return {
            "doc_id": self.build_doc_id(file_path),
            "file_name": file_path.name,
            "pages": pages,
            "page_count": len(pages),
        }

    def build_doc_id(self, file_path: Path) -> str:
        digest = hashlib.sha1(f"{file_path.name}:{file_path.stat().st_size}".encode("utf-8")).hexdigest()
        return digest[:16]

    def _table_to_markdown(self, table: list[list[str | None]]) -> str:
        normalized_rows = []
        for row in table:
            normalized_rows.append([self._clean_cell(cell) for cell in row])

        if not normalized_rows:
            return ""

        header = normalized_rows[0]
        separator = ["---" for _ in header]
        body = normalized_rows[1:] if len(normalized_rows) > 1 else []

        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for row in body:
            padded_row = row + [""] * max(0, len(header) - len(row))
            lines.append("| " + " | ".join(padded_row[: len(header)]) + " |")
        return "\n".join(lines)

    def _clean_cell(self, value: str | None) -> str:
        return (value or "").replace("\n", " ").strip()
