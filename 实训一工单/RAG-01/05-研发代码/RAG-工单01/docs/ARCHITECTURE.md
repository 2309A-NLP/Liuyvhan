# 项目整体架构设计

## 1. 总体架构

```text
PDF上传/放置
    ↓
PDF解析(pdfplumber)
    ↓
文本+表格清洗
    ↓
文档切块(Chunk)
    ↓
向量化(sentence-transformers)
    ↓
Milvus建库检索
    ↓
RAG Prompt组装
    ↓
LLM生成答案
    ↓
API返回答案+来源页码+相似度
```

## 2. 技术选型

- Web API：FastAPI
- PDF解析：pdfplumber
- 向量模型：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 向量数据库：Milvus
- 缓存：Redis
- 反馈存储：MySQL，可降级为本地 JSONL
- 大模型：OpenAI 兼容接口
- 评估：RAGAS

## 3. 核心模块

### 3.1 PDF 解析模块

- 提取页面文本
- 提取表格并转为 Markdown 文本
- 将页面文本与表格文本合并，供后续切块

### 3.2 切块与向量化模块

- 默认 chunk size 为 700 字符
- 默认 overlap 为 120 字符
- 每个 chunk 保留 `file_name`、`page`、`chunk_index`、`content`
- 向量化后写入 Milvus

### 3.3 检索增强生成模块

- 将用户问题编码为向量
- 从 Milvus 检索 top-k 相关 chunk
- 使用 BM25 做关键词召回
- 融合向量召回与 BM25 召回结果
- 使用 reranker 对融合结果进行二阶段重排
- 将命中 chunk 拼接成上下文
- 传入 LLM 生成最终答案
- 输出来源片段、页码、相似度

### 3.4 性能设计

- Redis 缓存高频问题结果
- top-k 默认设置为 5
- 使用轻量多语向量模型以兼顾速度和中英文支持
- 文档入库与问答分离，问答阶段只做向量检索和生成
- 对招股书数字、标准名称、募集资金等关键词问题增加 BM25 召回
- 服务启动时自动从 `data/processed` 恢复 BM25 索引，减少重复入库操作

## 4. API 设计

- `POST /api/v1/documents/upload`：上传 PDF
- `POST /api/v1/documents/index`：构建索引
- `GET /api/v1/documents/status`：查看已入库文档
- `POST /api/v1/chat/rag`：RAG 问答
- `POST /api/v1/chat/llm`：纯 LLM 问答
- `POST /api/v1/feedback`：用户反馈
- `POST /api/v1/evaluation/run`：运行 10 问评估

## 5. 开发流程

1. 配置 `.env`
2. 放置 PDF 到 `data/raw/`
3. 调用索引接口
4. 调用问答接口
5. 调用评估接口
6. 查看 `data/exports/` 导出的 CSV/JSON 结果
