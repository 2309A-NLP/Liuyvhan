import hashlib
import re
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
                # 工单编号：人工智能 NLP-RAG-PDF 文档的表格解析及检索优化
                # 同时提取正文、表格 Markdown 和表格行文本，提升字段类问题的召回能力。
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                tables = page.extract_tables() or []
                table_blocks = [
                    self._build_table_block(table=table, table_index=table_index)
                    for table_index, table in enumerate(tables, start=1)
                    if table
                ]
                blocks = self._build_page_blocks(page_text=page_text, table_blocks=table_blocks)
                table_texts = [block["content"] for block in table_blocks if block["content"].strip()]
                merged_text = "\n\n".join(block["content"] for block in blocks if block["content"].strip())
                pages.append(
                    {
                        "page": page_index,
                        "text": merged_text.strip(),
                        "raw_text": page_text.strip(),
                        "tables": table_texts,
                        "blocks": blocks,
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

    def extract_first_page_text(self, file_path: Path) -> str:
        with pdfplumber.open(file_path) as pdf:
            if not pdf.pages:
                return ""
            return (pdf.pages[0].extract_text(x_tolerance=2, y_tolerance=2) or "").strip()

    def _build_page_blocks(self, page_text: str, table_blocks: list[dict]) -> list[dict]:
        blocks: list[dict] = []
        cleaned_page_text = page_text.strip()
        if cleaned_page_text:
            blocks.append(
                {
                    "block_type": "page_text",
                    "block_index": 0,
                    "content": cleaned_page_text,
                }
            )

        blocks.extend(table_blocks)
        return blocks

    def _build_table_block(self, table: list[list[str | None]], table_index: int) -> dict:
        markdown = self._table_to_markdown(table)
        row_text = self._table_to_row_text(table)
        content_parts = [f"【表格 {table_index}】"]
        if markdown:
            content_parts.append(markdown)
        if row_text:
            content_parts.append("【表格行文本】\n" + row_text)
        return {
            "block_type": "table",
            "block_index": table_index,
            "content": "\n".join(part for part in content_parts if part.strip()).strip(),
        }

    def _table_to_markdown(self, table: list[list[str | None]]) -> str:
        normalized_rows = [self._normalize_row(row) for row in table]
        normalized_rows = [row for row in normalized_rows if row]

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

    def _table_to_row_text(self, table: list[list[str | None]]) -> str:
        normalized_rows = [self._normalize_row(row) for row in table]
        normalized_rows = [row for row in normalized_rows if row]
        if not normalized_rows:
            return ""

        if len(normalized_rows) == 1:
            return " | ".join(normalized_rows[0])

        header = normalized_rows[0]
        body = normalized_rows[1:]
        lines: list[str] = []

        if self._looks_like_header(header=header, body=body):
            for row in body:
                cells: list[str] = []
                for index, value in enumerate(row):
                    column_name = header[index] if index < len(header) else f"列{index + 1}"
                    cells.append(f"{column_name}: {value}")
                if cells:
                    lines.append("；".join(cells))
            return "\n".join(lines)

        for row in normalized_rows:
            lines.append(" | ".join(row))
        return "\n".join(lines)

    def _normalize_row(self, row: list[str | None]) -> list[str]:
        cleaned = [self._clean_cell(cell) for cell in row]
        return [cell for cell in cleaned if cell]

    def _looks_like_header(self, header: list[str], body: list[list[str]]) -> bool:
        if not header or not body:
            return False

        header_text = "".join(header)
        if any(token in header_text for token in ["序号", "名称", "项目", "金额", "比例", "关系", "股东", "年份", "收入"]):
            return True

        return all(len(row) <= len(header) for row in body[:5])

    def _clean_cell(self, value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "").replace("\n", " ")).strip()
