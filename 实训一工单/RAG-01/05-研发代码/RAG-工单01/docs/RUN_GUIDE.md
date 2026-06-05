# 运行说明

## 1. 环境要求

- Python 环境：`D:\Anaconda\envs\RAG`
- 已启动服务：
  - Milvus
  - Redis
  - MySQL（可选）

## 2. 数据目录

- `data/raw/`：原始 PDF
- `data/processed/`：分块和索引清单
- `data/exports/`：评估结果与导出数据

## 3. 配置步骤

1. 复制 `.env.example` 为 `.env`
2. 填写核心配置：

```env
MILVUS_URI=http://127.0.0.1:19530
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_CACHE_TTL=3600
REDIS_MEMORY_TTL=7200
CONVERSATION_HISTORY_LIMIT=6
LLM_API_KEY=你的密钥
LLM_BASE_URL=你的OpenAI兼容接口地址
LLM_MODEL=gpt-4o-mini
MYSQL_ENABLED=false
```

如果要启用 MySQL：

```env
MYSQL_ENABLED=true
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的密码
MYSQL_DATABASE=rag_ticket01
```

## 4. 安装依赖

```powershell
conda activate RAG
pip install -r requirements.txt
```

## 5. 启动服务

```powershell
conda activate RAG
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 6. 推荐调用顺序

1. 将 `招股说明书1.pdf` 放入 `data/raw/`
2. 调用 `POST /api/v1/documents/index`
3. 调用 `POST /api/v1/chat/rag`
4. 如需多轮追问，携带同一个 `session_id`
5. 如需对照，调用 `POST /api/v1/chat/llm`
6. 如需评估，调用 `POST /api/v1/evaluation/run`

## 7. 多轮会话短期记忆说明

Redis 现在承担两类能力：

1. 问答结果缓存
2. 按 `session_id` 保存最近几轮会话历史

示例：

```json
{
  "session_id": "demo-user-001",
  "question": "武汉兴图新科电子股份有限公司注册资本是多少？",
  "file_name": "招股说明书1.pdf"
}
```

继续追问：

```json
{
  "session_id": "demo-user-001",
  "question": "法定代表人是谁？",
  "file_name": "招股说明书1.pdf"
}
```

清空该会话历史：

```json
{
  "session_id": "demo-user-001",
  "clear_history": true,
  "question": "重新开始，公司主营业务是什么？",
  "file_name": "招股说明书1.pdf"
}
```

## 8. API 调试方式

- Postman：导入 `docs/POSTMAN_COLLECTION.json`
- Swagger：`http://127.0.0.1:8000/docs`
