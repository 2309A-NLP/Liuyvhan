## CCF Competition Workspace

Put the extracted competition PDFs into:

- `data/ccf_competition/raw/`

Recommended `.env` switch:

```ini
RAW_DATA_DIR=./data/ccf_competition/raw
PROCESSED_DATA_DIR=./data/ccf_competition/processed
IMAGE_DATA_DIR=./data/ccf_competition/processed/images
EXPORT_DIR=./data/ccf_competition/exports
MILVUS_COLLECTION=ccf_competition_chunks_20260609
DEFAULT_FILE_NAME=<one_pdf_name>.pdf
```

Commands after PDFs are ready:

```powershell
python run_uvicorn.py
python scripts/reindex_all.py
```

Evaluation question files:

- `data/ccf_competition/processed/evaluation_questions.json`
- `data/ccf_competition/processed/evaluation_questions.example.json`

Keep the CCF collection separate from the old knowledge base. Do not reuse the previous
`MILVUS_COLLECTION` unless you intentionally want mixed retrieval results.
