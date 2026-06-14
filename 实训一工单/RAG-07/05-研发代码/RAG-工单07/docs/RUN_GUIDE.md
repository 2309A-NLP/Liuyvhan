# 运行说明

## 1. 环境要求

- Python 环境：`D:\Anaconda\envs\RAG`
- 已启动服务：
  - Milvus
  - Redis
  - MySQL（可选）

## 2. 数据目录

你后续放项目数据的目录已经建立：

- `data/raw/`：原始 PDF
- `data/processed/`：切块和索引清单
- `data/exports/`：评估结果与反馈导出

## 3. 配置步骤

1. 复制 `.env.example` 为 `.env`
2. 重点填写以下配置：

```env
MILVUS_URI=http://127.0.0.1:19530
REDIS_URL=redis://127.0.0.1:6379/0
LLM_API_KEY=你的密钥
LLM_BASE_URL=你的OpenAI兼容接口地址
LLM_MODEL=gpt-4o-mini
MYSQL_ENABLED=false
```

如果需要把反馈写入本地 MySQL，则改为：

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

## 6. 调用顺序

1. 将 `招股说明书1.pdf` 放到 `data/raw/`
2. 调用 `POST /api/v1/documents/index`
3. 调用 `POST /api/v1/chat/rag`
4. 如需对照，调用 `POST /api/v1/chat/llm`
5. 如需评估，调用 `POST /api/v1/evaluation/run`

## 7. Postman 使用

导入文件：

[docs/POSTMAN_COLLECTION.json](/c:/Users/刘禹含/Desktop/RAG-工单01/docs/POSTMAN_COLLECTION.json)

也可以直接访问 Swagger：

`http://127.0.0.1:8000/docs`
