# RAG-工单01

基于《招股说明书1.pdf》的 RAG 问答后端项目，支持 PDF 解析、向量检索、LLM 生成、Postman 调用、RAGAS 评估。

## 项目概述

本项目面向企业招股书问答场景，完成了从 PDF 文档到可检索知识库的完整链路，并提供标准 HTTP 接口供 Postman 或其他客户端调用。

## 核心能力

- PDF 解析：提取正文与表格
- 文档切块：将长文档拆分为检索块
- 向量化：将文本转换为向量
- 向量库：使用 Milvus 存储与检索
- 问答生成：使用大模型基于检索结果回答
- 反馈记录：支持 MySQL 或本地 JSONL
- 效果评估：支持 RAGAS

## 技术选型

- Web 框架：FastAPI
- PDF 解析：pdfplumber
- 向量模型：sentence-transformers
- 向量数据库：Milvus
- 缓存：Redis
- 数据库：MySQL
- 大模型：阿里云百炼 OpenAI 兼容接口
- 评估：RAGAS

## 目录结构

```text
app/                后端代码
data/raw/           原始 PDF
data/processed/     切块与索引文件
data/exports/       评估与反馈输出
docs/               架构、使用、升级文档
scripts/            评估脚本
```

## 快速启动

1. 配置 `.env`
2. 放入 `招股说明书1.pdf`
3. 启动服务

```powershell
conda activate RAG
D:\Anaconda\envs\RAG\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 主要接口

- `GET /api/v1/health`
- `POST /api/v1/documents/upload`
- `POST /api/v1/documents/index`
- `POST /api/v1/chat/rag`
- `POST /api/v1/chat/llm`
- `POST /api/v1/feedback`
- `POST /api/v1/evaluation/run`

## 使用说明

1. 上传或放置 PDF 到 `data/raw/`
2. 调用 `/api/v1/documents/index` 建库
3. 调用 `/api/v1/chat/rag` 提问
4. 调用 `/api/v1/chat/llm` 做纯 LLM 对照
5. 调用 `/api/v1/evaluation/run` 输出评估结果

## 文档

- [架构说明](docs/ARCHITECTURE.md)
- [用户手册](docs/USER_MANUAL.md)
- [企业升级方案](docs/ENTERPRISE_UPGRADE_PLAN.md)
- [评估说明](docs/EVALUATION.md)

