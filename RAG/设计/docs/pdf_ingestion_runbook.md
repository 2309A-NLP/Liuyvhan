# PDF Import Runbook

## Scope

This project now has a standalone PDF ingestion script for offline knowledge import.

Current v1 capabilities:

- Extract text directly from text-based PDF files
- Remove repeated header/footer style lines across pages
- Remove simple page number / watermark-like noise lines
- Optional OCR fallback for scanned pages
- Optional embedded image export with page metadata
- Reuse the existing embedding + Milvus knowledge import flow

Current v1 limitations:

- No true chart semantic understanding yet
- No table structure reconstruction yet
- No guaranteed watermark removal for every complex layout
- OCR depends on local `tesseract` binary and language packs

## New Files

- `utils/pdf_cleaner.py`
- `utils/pdf_parser.py`
- `scripts/import_pdf_knowledge.py`

## Dependencies

Install the new Python dependencies in your current environment:

```cmd
D:\Anaconda\envs\RAG\python.exe -m pip install PyMuPDF==1.24.13 pytesseract==0.3.13 Pillow==12.2.0
```

If you want OCR, you also need to install local Tesseract separately.

## Import Command

Basic import:

```cmd
D:\Anaconda\envs\RAG\python.exe C:\Users\刘禹含\Desktop\RAG\scripts\import_pdf_knowledge.py --pdf-path "C:\Users\刘禹含\Desktop\医疗数据集\example.pdf" --role-id doctor
```

Import with OCR:

```cmd
D:\Anaconda\envs\RAG\python.exe C:\Users\刘禹含\Desktop\RAG\scripts\import_pdf_knowledge.py --pdf-path "C:\Users\刘禹含\Desktop\医疗数据集\example.pdf" --role-id doctor --ocr --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Import with image export and preview JSON:

```cmd
D:\Anaconda\envs\RAG\python.exe C:\Users\刘禹含\Desktop\RAG\scripts\import_pdf_knowledge.py --pdf-path "C:\Users\刘禹含\Desktop\医疗数据集\example.pdf" --role-id doctor --extract-images --image-output-dir "C:\Users\刘禹含\Desktop\RAG\data\pdf_images\example" --preview-json "C:\Users\刘禹含\Desktop\RAG\data\pdf_preview\example.json"
```

## What The Script Does

1. Parse the PDF page by page
2. Extract text
3. If enabled, run OCR on pages with too little text
4. Clean repeated header/footer noise
5. Split cleaned page text into chunks
6. Call your current embedding service
7. Write chunks into Milvus `role_knowledge`

## Notes

- This script does not modify `main.py`
- This script does not change your FastAPI routes
- It is an offline import tool only
- Imported chunks are tied to one `role_id`
- If the role is missing in MySQL, the script warns but can still import into Milvus
- `--reset-knowledge` resets the whole knowledge collection, so use it carefully

## Auto Import Mode

The project now also supports lightweight startup-time PDF auto import.

Default behavior:

- Scan `data/raw_pdfs/` when `main.py` starts
- Import only new or changed PDF files
- Do not block FastAPI startup
- Do not run OCR by default
- Save import state to `data/storage/pdf_import_state.json`

Role mapping rules:

- Preferred: `data/raw_pdfs/<role_id>/xxx.pdf`
- Fallback: use `PDF_AUTO_IMPORT_DEFAULT_ROLE_ID`

Example:

- `data/raw_pdfs/doctor/example.pdf`

Optional `.env` switches:

```env
PDF_AUTO_IMPORT_ENABLED=true
PDF_AUTO_IMPORT_DEFAULT_ROLE_ID=doctor
```
