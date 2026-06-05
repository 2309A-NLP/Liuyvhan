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
        current_section_title = ""

        with pdfplumber.open(file_path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                tables = page.extract_tables() or []
                table_texts = [self._table_to_markdown(table) for table in tables if table]
                merged_text = "\n\n".join([value for value in [page_text, *table_texts] if value.strip()])

                detected_title = self._detect_section_title(page_text)
                if detected_title:
                    current_section_title = detected_title

                pages.append(
                    {
                        "page": page_index,
                        "text": merged_text.strip(),
                        "raw_text": page_text.strip(),
                        "tables": table_texts,
                        "section_title": current_section_title,
                        "segments": self._build_segments(
                            page_text=page_text,
                            table_texts=table_texts,
                            section_title=current_section_title,
                        ),
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

    def _build_segments(self, page_text: str, table_texts: list[str], section_title: str) -> list[dict]:
        segments: list[dict] = []

        for paragraph in self._split_paragraphs(page_text):
            segment_title = self._extract_local_heading(paragraph) or section_title
            segments.append(
                {
                    "type": "text",
                    "content": paragraph,
                    "section_title": segment_title,
                }
            )

        for table_text in table_texts:
            cleaned_table = table_text.strip()
            if cleaned_table:
                segments.append(
                    {
                        "type": "table",
                        "content": cleaned_table,
                        "section_title": section_title,
                    }
                )

        if not segments and page_text.strip():
            segments.append(
                {
                    "type": "text",
                    "content": page_text.strip(),
                    "section_title": section_title,
                }
            )

        return segments

    def _split_paragraphs(self, text: str) -> list[str]:
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not cleaned:
            return []

        paragraphs: list[str] = []
        current_lines: list[str] = []

        for raw_line in cleaned.split("\n"):
            line = raw_line.strip()
            if not line:
                if current_lines:
                    paragraphs.append("\n".join(current_lines))
                    current_lines = []
                continue

            current_lines.append(line)
            if self._is_paragraph_boundary(line):
                paragraphs.append("\n".join(current_lines))
                current_lines = []

        if current_lines:
            paragraphs.append("\n".join(current_lines))

        return [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]

    def _is_paragraph_boundary(self, line: str) -> bool:
        if len(line) >= 40:
            return True
        if line.endswith(("。", "；", "：", ".", ";", ":")):
            return True
        if self._looks_like_heading(line):
            return True
        return False

    def _detect_section_title(self, page_text: str) -> str:
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if self._looks_like_heading(line):
                return self._normalize_heading(line)
        return ""

    def _extract_local_heading(self, paragraph: str) -> str:
        first_line = paragraph.splitlines()[0].strip()
        if self._looks_like_heading(first_line):
            return self._normalize_heading(first_line)
        return ""

    def _looks_like_heading(self, line: str) -> bool:
        if not line or len(line) > 40:
            return False

        patterns = [
            r"^第[一二三四五六七八九十百零0-9]+节",
            r"^第[一二三四五六七八九十百零0-9]+章",
            r"^[一二三四五六七八九十]+、",
            r"^（[一二三四五六七八九十0-9]+）",
            r"^\([一二三四五六七八九十0-9]+\)",
            r"^[0-9]+[.、]",
        ]
        return any(re.match(pattern, line) for pattern in patterns)

    def _normalize_heading(self, line: str) -> str:
        return re.sub(r"\s+", " ", line).strip()
