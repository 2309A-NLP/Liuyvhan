# RAG 工单 04

这是一个基于 FastAPI 的 PDF RAG 问答后端，当前版本已按工单“人工智能 NLP-RAG-图像内容解析及检索优化”扩展了多模态能力。

## 当前能力

- PDF 正文解析
- PDF 表格解析
- PDF 图片语义解析
- BM25 + 向量混合检索
- 基于检索上下文的答案生成
- 评估与反馈接口

## 图像语义解析

工单 04 的关键改动已经接入现有索引链路：

- 使用 `CLIP` 对 PDF 中的图片做语义标签分类
- 可选使用多模态大模型对图片做补充描述
- 将图片语义结果写入与正文、表格一致的 chunk
- 图片相关问题在检索时会对 `image` block 做额外加权

图片解析结果会落到 `data/processed/images/`。

## 依赖

除了原有依赖，图像解析新增：

- `pillow`
- `transformers`
- `torch`

如果要启用多模态大模型描述，还需要配置：

- `LLM_API_KEY`
- 可选 `MULTIMODAL_MODEL`
- `ENABLE_VLM_IMAGE_SEMANTICS=true`

## 关键配置

可通过 `.env` 覆盖以下配置：

- `ENABLE_MULTIMODAL_IMAGE_PARSING`
- `ENABLE_CLIP_IMAGE_SEMANTICS`
- `ENABLE_VLM_IMAGE_SEMANTICS`
- `CLIP_MODEL_NAME`
- `CLIP_MODEL_PATH`
- `MULTIMODAL_MODEL`
- `MAX_IMAGES_PER_PAGE`
- `MIN_IMAGE_WIDTH`
- `MIN_IMAGE_HEIGHT`

## 启动

```powershell
conda activate RAG
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 使用

1. 将 `招股说明书1.pdf`、`招股说明书2.pdf` 放入 `data/raw/`
2. 调用 `POST /api/v1/documents/index` 建索引
3. 调用 `POST /api/v1/chat/rag` 提问

## 接口

- `GET /api/v1/health`
- `POST /api/v1/documents/upload`
- `POST /api/v1/documents/index`
- `POST /api/v1/chat/rag`
- `POST /api/v1/chat/llm`
- `POST /api/v1/feedback`
- `POST /api/v1/evaluation/run`
