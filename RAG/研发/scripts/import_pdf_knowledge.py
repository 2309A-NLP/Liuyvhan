from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import SETTINGS
from core.embedding import EmbeddingService
from database.milvus_client import MilvusClient
from database.mysql_client import MySQLClient
from utils.logger import get_logger
from utils.pdf_parser import PDFParser
from utils.text_splitter import TextSplitter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a PDF file into the RAG knowledge base.")
    parser.add_argument("--pdf-path", required=True, help="Absolute or relative path to the PDF file.")
    parser.add_argument("--role-id", required=True, help="Role id to bind this knowledge to.")
    parser.add_argument("--title", default="", help="Document title. Defaults to the PDF filename.")
    parser.add_argument("--source", default="", help="Source label stored in Milvus.")
    parser.add_argument("--doc-id", default="", help="Stable document prefix. Defaults to pdf_<filename>.")
    parser.add_argument("--reset-knowledge", action="store_true", help="Reset the whole knowledge collection first.")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR fallback for image/scanned pages.")
    parser.add_argument("--ocr-lang", default="chi_sim+eng", help="Tesseract OCR language pack.")
    parser.add_argument("--tesseract-cmd", default="", help="Optional absolute path to tesseract.exe.")
    parser.add_argument("--extract-images", action="store_true", help="Export embedded page images.")
    parser.add_argument("--image-output-dir", default="", help="Directory to save extracted page images.")
    parser.add_argument("--preview-json", default="", help="Optional path to save parsed PDF preview JSON.")
    parser.add_argument("--chunk-size", type=int, default=220, help="Chunk size in characters.")
    parser.add_argument("--chunk-overlap", type=int, default=40, help="Chunk overlap in characters.")
    parser.add_argument("--min-text-chars", type=int, default=40, help="OCR fallback threshold per page.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger = get_logger("import_pdf_knowledge")

    mysql_client = MySQLClient(SETTINGS, logger)
    mysql_client.init_schema()
    if not mysql_client.role_exists(args.role_id):
        logger.warning("Role does not exist in MySQL yet. role_id=%s", args.role_id)

    milvus_client = MilvusClient(SETTINGS, logger)
    embedding_service = EmbeddingService(SETTINGS, logger)
    milvus_client.ensure_collection(SETTINGS.knowledge_collection)

    if args.reset_knowledge:
        milvus_client.reset_collection(SETTINGS.knowledge_collection)
        logger.warning("Knowledge collection reset before PDF import.")

    pdf_path = Path(args.pdf_path).expanduser().resolve()
    image_output_dir = Path(args.image_output_dir).expanduser().resolve() if args.image_output_dir else None

    parser = PDFParser(
        ocr_enabled=args.ocr,
        ocr_lang=args.ocr_lang,
        tesseract_cmd=args.tesseract_cmd,
        extract_images=args.extract_images,
        image_output_dir=image_output_dir,
        min_text_chars=args.min_text_chars,
        logger=logger,
    )
    parsed = parser.parse(pdf_path)

    if args.preview_json:
        preview_path = Path(args.preview_json).expanduser().resolve()
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_text(json.dumps(parsed.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("PDF preview JSON saved to %s", preview_path)

    title = args.title.strip() or pdf_path.stem
    source = args.source.strip() or str(pdf_path)
    doc_prefix = args.doc_id.strip() or _build_default_doc_id(pdf_path)
    splitter = TextSplitter(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)

    chunk_records: list[dict] = []
    for page in parsed.pages:
        if not page.text.strip():
            continue
        chunks = splitter.split(page.text)
        vectors = embedding_service.embed_texts(chunks).tolist()
        for index, (chunk, vector) in enumerate(zip(chunks, vectors), start=1):
            chunk_records.append(
                {
                    "doc_id": f"{doc_prefix}-p{page.page_number}-c{index}",
                    "title": title,
                    "content": chunk,
                    "source": source,
                    "vector": vector,
                    "role_id": args.role_id,
                    "user_id": "",
                    "doc_metadata": {
                        "origin": "pdf",
                        "pdf_path": str(pdf_path),
                        "page_number": page.page_number,
                        "used_ocr": page.used_ocr,
                        "image_count": page.image_count,
                        "images": [image.filename for image in page.images],
                    },
                }
            )

    if not chunk_records:
        raise RuntimeError("No usable text was extracted from the PDF.")

    inserted = milvus_client.upsert_documents(SETTINGS.knowledge_collection, chunk_records)
    summary = {
        "status": "ok",
        "pdf_path": str(pdf_path),
        "role_id": args.role_id,
        "title": title,
        "pages": parsed.page_count,
        "chunks": inserted,
        "ocr_enabled": args.ocr,
        "extract_images": args.extract_images,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _build_default_doc_id(pdf_path: Path) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", pdf_path.stem).strip("_").lower()
    return f"pdf_{stem or 'document'}"


if __name__ == "__main__":
    main()
