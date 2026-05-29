from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from utils.pdf_parser import PDFParser
from utils.text_splitter import TextSplitter


class PDFAutoImportManager:
    """Lightweight startup-time PDF auto import manager."""

    def __init__(self, settings, mysql_client, milvus_client, embedding_service, logger):
        self.settings = settings
        self.mysql_client = mysql_client
        self.milvus_client = milvus_client
        self.embedding_service = embedding_service
        self.logger = logger
        self.splitter = TextSplitter(chunk_size=220, chunk_overlap=40)
        self.parser = PDFParser(
            ocr_enabled=False,
            extract_images=False,
            min_text_chars=40,
            logger=logger,
        )

    def run_once(self) -> dict[str, int]:
        if not self.settings.pdf_auto_import_enabled:
            self.logger.info("PDF auto import disabled.")
            return {"scanned": 0, "imported": 0, "skipped": 0, "failed": 0}

        root = self.settings.raw_pdf_dir
        root.mkdir(parents=True, exist_ok=True)
        state = self._load_state()

        scanned = imported = skipped = failed = 0
        pdf_files = sorted(root.rglob("*.pdf"))
        for pdf_path in pdf_files:
            scanned += 1
            try:
                if not pdf_path.is_file():
                    skipped += 1
                    continue

                fingerprint = self._build_fingerprint(pdf_path)
                role_id = self._resolve_role_id(pdf_path)
                if not role_id:
                    self.logger.warning("Skip PDF without role mapping. path=%s", pdf_path)
                    skipped += 1
                    continue

                state_key = str(pdf_path.resolve())
                previous = state.get(state_key)
                if previous and previous.get("fingerprint") == fingerprint and previous.get("status") == "imported":
                    skipped += 1
                    continue

                chunk_count = self._import_pdf(pdf_path, role_id)
                state[state_key] = {
                    "status": "imported",
                    "fingerprint": fingerprint,
                    "role_id": role_id,
                    "chunks": chunk_count,
                }
                self._save_state(state)
                imported += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.logger.exception("PDF auto import failed. path=%s error=%s", pdf_path, exc)
                state[str(pdf_path.resolve())] = {
                    "status": "failed",
                    "error": str(exc),
                }
                self._save_state(state)

        self.logger.info(
            "PDF auto import summary scanned=%s imported=%s skipped=%s failed=%s",
            scanned,
            imported,
            skipped,
            failed,
        )
        return {
            "scanned": scanned,
            "imported": imported,
            "skipped": skipped,
            "failed": failed,
        }

    def get_status(self) -> dict[str, Any]:
        state = self._load_state()
        entries: list[dict[str, Any]] = []
        for pdf_path, item in sorted(state.items()):
            record = dict(item)
            record["pdf_path"] = pdf_path
            entries.append(record)
        summary = {
            "tracked": len(entries),
            "imported": sum(1 for item in entries if item.get("status") == "imported"),
            "failed": sum(1 for item in entries if item.get("status") == "failed"),
        }
        return {"summary": summary, "items": entries}

    def _import_pdf(self, pdf_path: Path, role_id: str) -> int:
        parsed = self.parser.parse(pdf_path)
        title = pdf_path.stem
        source = str(pdf_path)
        doc_prefix = f"pdf_{self._safe_name(pdf_path.stem)}"

        chunk_records: list[dict[str, Any]] = []
        for page in parsed.pages:
            if not page.text.strip():
                continue
            chunks = self.splitter.split(page.text)
            vectors = self.embedding_service.embed_texts(chunks).tolist()
            for index, (chunk, vector) in enumerate(zip(chunks, vectors), start=1):
                chunk_records.append(
                    {
                        "doc_id": f"{doc_prefix}-p{page.page_number}-c{index}",
                        "title": title,
                        "content": chunk,
                        "source": source,
                        "vector": vector,
                        "role_id": role_id,
                        "user_id": "",
                        "doc_metadata": {
                            "origin": "pdf_auto_import",
                            "pdf_path": str(pdf_path),
                            "page_number": page.page_number,
                            "used_ocr": page.used_ocr,
                            "image_count": page.image_count,
                        },
                    }
                )

        if not chunk_records:
            raise RuntimeError("No usable text was extracted from the PDF.")

        preview_path = self.settings.pdf_preview_dir / f"{pdf_path.stem}.json"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_text(json.dumps(parsed.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

        self.milvus_client.ensure_collection(self.settings.knowledge_collection)
        self.milvus_client.upsert_documents(self.settings.knowledge_collection, chunk_records)
        self.logger.info(
            "PDF auto imported role_id=%s path=%s chunks=%s",
            role_id,
            pdf_path,
            len(chunk_records),
        )
        return len(chunk_records)

    def _resolve_role_id(self, pdf_path: Path) -> str:
        relative = pdf_path.resolve().relative_to(self.settings.raw_pdf_dir.resolve())
        parts = list(relative.parts)
        if len(parts) >= 2:
            candidate = parts[0].strip()
            if candidate and self.mysql_client.role_exists(candidate):
                return candidate

        default_role = self.settings.pdf_auto_import_default_role_id.strip()
        if default_role and self.mysql_client.role_exists(default_role):
            return default_role

        stem = self._safe_name(pdf_path.stem)
        if self.mysql_client.role_exists(stem):
            return stem

        return ""

    def _load_state(self) -> dict[str, Any]:
        path = self.settings.pdf_import_state_path
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.logger.warning("PDF import state file is invalid JSON. path=%s", path)
            return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        path = self.settings.pdf_import_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _build_fingerprint(pdf_path: Path) -> str:
        stat = pdf_path.stat()
        payload = f"{pdf_path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value.lower())
        return cleaned.strip("_") or "document"
