# 运行与部署说明

## 当前可用版本

- 主服务：`main.py`，端口 `8001`
- 本地 embedding 服务：`local_embedding_service.py`，端口 `8002`
- 本地 rerank 服务：`local_rerank_service.py`，端口 `8003`
- MySQL：`127.0.0.1:3306`，数据库 `ragdata`
- Redis：`127.0.0.1:6379`
- Milvus：`http://127.0.0.1:19530`

## 当前配置

```env
APP_PORT=8001
PYTHON_EXE=D:\Anaconda\envs\RAG\python.exe
DB_BACKEND=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=root
MYSQL_DATABASE=ragdata
REDIS_ENABLED=true
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
MILVUS_ENABLED=true
MILVUS_URI=http://127.0.0.1:19530
EMBEDDING_BACKEND=remote_api
EMBEDDING_MODEL_NAME=moka-ai/m3e-base
EMBEDDING_API_URL=http://127.0.0.1:8002/embeddings
EMBEDDING_DIMENSION=768
LOCAL_EMBEDDING_MODEL_PATH=D:\models\m3e-base
LOCAL_EMBEDDING_SERVICE_PORT=8002
RERANK_BACKEND=remote_api
RERANK_MODEL_NAME=BAAI/bge-reranker-v2-m3
RERANK_API_URL=http://127.0.0.1:8003/rerank
LOCAL_RERANK_MODEL_PATH=BAAI/bge-reranker-v2-m3
LOCAL_RERANK_SERVICE_PORT=8003
```

## 启动顺序

1. 启动 Redis
2. 启动 MySQL
3. 启动 Milvus
4. 启动 `local_embedding_service.py`
5. 启动 `local_rerank_service.py`
6. 启动 `main.py`

## 启动命令

```cmd
D:\Anaconda\envs\RAG\python.exe C:\Users\刘禹含\Desktop\RAG\local_embedding_service.py
D:\Anaconda\envs\RAG\python.exe C:\Users\刘禹含\Desktop\RAG\local_rerank_service.py
D:\Anaconda\envs\RAG\python.exe C:\Users\刘禹含\Desktop\RAG\main.py
```

## 验证地址

- `http://127.0.0.1:8002/health`
- `http://127.0.0.1:8003/health`
- `http://127.0.0.1:8001/health`
- `POST http://127.0.0.1:8001/chat`
- `POST http://127.0.0.1:8001/knowledge/reload`

## PDF 离线入库

- 导入脚本：`scripts/import_pdf_knowledge.py`
- 说明文档：`docs/pdf_ingestion_runbook.md`

## 现阶段说明

- `m3e-base` 已接入为本地 embedding 服务
- `Milvus` 已切到 `768` 维
- `role_knowledge` 已可重建并正常检索
- `rerank` 已新增独立服务入口，后续只需替换成真正的 `BGE-reranker` 服务
- 如果你把 `LOCAL_RERANK_MODEL_PATH` 设成 `BAAI/bge-reranker-v2-m3`，它会尝试自动下载并在本机 CPU 上运行；卡顿就改回轻量版
