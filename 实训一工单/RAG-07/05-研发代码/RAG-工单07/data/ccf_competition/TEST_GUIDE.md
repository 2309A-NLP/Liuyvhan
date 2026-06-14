# CCF Competition Test Guide

## 1. Path Switch

Do not overwrite the current default knowledge-base config directly until you finish the CCF test.
Use an isolated configuration in `.env`:

```ini
RAW_DATA_DIR=./data/ccf_competition/raw
PROCESSED_DATA_DIR=./data/ccf_competition/processed
IMAGE_DATA_DIR=./data/ccf_competition/processed/images
EXPORT_DIR=./data/ccf_competition/exports
MILVUS_COLLECTION=ccf_competition_chunks_20260609
DEFAULT_FILE_NAME=<one_pdf_name>.pdf
```

Code locations that read these values:

- `app/core/config.py`
- `app/services/rag_service.py`
- `app/services/vector_store.py`
- `app/services/evaluation_service.py`

Notes:

- You do need to rebuild the index after switching to the new PDF folder.
- Do not reuse the previous `MILVUS_COLLECTION`, otherwise old vectors can remain in the same collection and affect retrieval.
- `scripts/reindex_all.py` and `run_uvicorn.py` have been fixed to use the current project path instead of an old hardcoded path.
- If the PDF filenames look garbled after unzip, it is still workable, but renaming them to clean names before indexing will make debugging easier.

## 2. Actual Test Questions

The evaluation JSON has been prepared at:

- `data/ccf_competition/processed/evaluation_questions.json`

Source documents currently observed in `data/ccf_competition/raw`:

- China Pacific Insurance 2021 annual report
- Guotai Junan 2021 annual report

Question design coverage:

- China Pacific Insurance: Q1-Q5
- Guotai Junan: Q6-Q10

Question types:

- Fact
- Summary
- List
- Numeric
- Process

## 3. Evaluation Template

| 问题编号 | 问题内容 | 检索到的top-3文档片段 | RAG生成答案 | 相关性评分(1-5) | 是否命中正确答案所在文档 | 问题分析 |
|---|---|---|---|---|---|---|
| Q1 |  | 1. 片段A；2. 片段B；3. 片段C |  |  | 是/否 |  |
| Q2 |  | 1. 片段A；2. 片段B；3. 片段C |  |  | 是/否 |  |

Recommended scoring rule:

- 5: correct document retrieved and answer is complete
- 4: correct document retrieved and answer is mostly correct
- 3: partially relevant retrieval or incomplete answer
- 2: weak retrieval alignment and mostly incorrect answer
- 1: wrong document or obvious hallucination

## 4. Analysis Framework

### Success

- The correct source document appears in top-3.
- The answer-bearing chunk is ranked high enough to support generation.
- The final answer matches the reference answer without obvious fabrication.

### Failure

- Wrong document retrieved.
- Correct document retrieved but wrong chunk ranked.
- Correct chunk retrieved but answer generation failed.

### Likely Causes

- Chunk size or overlap is not suitable for annual-report style text.
- Query wording does not match the expressions used in the report.
- Embedding similarity is weak for financial-report terminology.
- Important answers are inside long front-matter paragraphs or tables.
- Old vectors are mixed into the same Milvus collection.

### Improvement Suggestions

- Keep CCF data in an isolated raw/processed/export/Milvus namespace.
- Compare at least two chunk settings, such as `700/120` and `500/100`.
- For questions with exact figures, check whether table blocks are being indexed cleanly.
- If retrieval often hits the wrong report, add company-name filtering or metadata filtering before vector search.
- Keep this 10-question set as a fixed regression benchmark for later tuning.

## 5. Run Steps

Start the API:

```powershell
python run_uvicorn.py
```

Rebuild the index:

```powershell
python scripts/reindex_all.py
```

Run evaluation through API:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/v1/evaluation/run `
  -ContentType "application/json" `
  -Body '{"questions_file":"./data/ccf_competition/processed/evaluation_questions.json","file_name":null,"top_k":5}'
```

Expected outputs:

- `data/ccf_competition/exports/`
- `data/exports/` if you keep the default export path in `.env`
