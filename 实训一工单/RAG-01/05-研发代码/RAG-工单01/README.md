# RAG-工单01

基于 PDF 招股书的 RAG 问答后端项目，支持 PDF 解析、混合检索、LLM 生成、评估，以及基于 Redis 的短期会话记忆。

## 项目能力

- PDF 文本与表格解析
- 结构感知分块
- 向量检索 + BM25 混合检索
- reranker 重排序
- 字段类问题结构化直答
- Redis 问答缓存
- Redis 会话级短期记忆
- RAGAS 评估

## 目录结构

```text
app/                后端代码
data/raw/           原始 PDF
data/processed/     分块与索引文件
data/exports/       评估输出
docs/               项目文档
scripts/            评估脚本
```

## 快速启动

1. 配置 `.env`
2. 将 PDF 放入 `data/raw/`
3. 启动 Milvus、Redis
4. 启动服务

```powershell
conda activate RAG
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 主要接口

- `GET /api/v1/health`
- `POST /api/v1/documents/upload`
- `POST /api/v1/documents/index`
- `POST /api/v1/chat/rag`
- `POST /api/v1/chat/llm`
- `POST /api/v1/feedback`
- `POST /api/v1/evaluation/run`

## Redis 短期记忆

项目现在支持基于 `session_id` 的多轮会话短期记忆。

### 功能说明

- 同一个 `session_id` 下，系统会把最近几轮用户问题和助手回答写入 Redis
- 后续追问会自动带上历史上下文
- 可通过 `clear_history=true` 清空该会话历史

### RAG 多轮问答示例

```json
{
  "session_id": "demo-user-001",
  "question": "武汉兴图新科电子股份有限公司注册资本是多少？",
  "file_name": "招股说明书1.pdf",
  "top_k": 5,
  "force_refresh": false
}
```

继续追问：

```json
{
  "session_id": "demo-user-001",
  "question": "法定代表人是谁？",
  "file_name": "招股说明书1.pdf",
  "top_k": 5
}
```

清空会话记忆：

```json
{
  "session_id": "demo-user-001",
  "clear_history": true,
  "question": "重新开始，公司主营业务是什么？",
  "file_name": "招股说明书1.pdf"
}
```

### 相关配置

```env
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_CACHE_TTL=3600
REDIS_MEMORY_TTL=7200
CONVERSATION_HISTORY_LIMIT=6
```

## 相关文档

- `docs/USER_MANUAL.md`
- `docs/RUN_GUIDE.md`
- `docs/FINAL_RAG_EVALUATION.md`
