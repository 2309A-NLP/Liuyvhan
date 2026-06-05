# 用户手册

## 1. 准备数据

将 PDF 放入：

`data/raw/`

也可以通过接口上传：

- `POST /api/v1/documents/upload`

## 2. 构建索引

请求地址：

`POST /api/v1/documents/index`

请求体：

```json
{
  "file_name": "招股说明书1.pdf",
  "rebuild": true
}
```

## 3. 发起单轮 RAG 问答

请求地址：

`POST /api/v1/chat/rag`

请求体：

```json
{
  "question": "武汉兴图新科电子股份有限公司注册资本是多少？",
  "file_name": "招股说明书1.pdf",
  "top_k": 5,
  "force_refresh": false
}
```

返回结果包含：

- `answer`：最终答案
- `sources`：命中来源片段
- `page`：来源页码
- `score`：相关分数

## 4. 发起带 Redis 短期记忆的多轮 RAG 问答

### 第一轮

```json
{
  "session_id": "demo-user-001",
  "question": "武汉兴图新科电子股份有限公司注册资本是多少？",
  "file_name": "招股说明书1.pdf",
  "top_k": 5
}
```

### 第二轮追问

```json
{
  "session_id": "demo-user-001",
  "question": "法定代表人是谁？",
  "file_name": "招股说明书1.pdf",
  "top_k": 5
}
```

### 清空历史后重新开始

```json
{
  "session_id": "demo-user-001",
  "clear_history": true,
  "question": "重新开始，公司主营业务是什么？",
  "file_name": "招股说明书1.pdf"
}
```

说明：

- `session_id` 相同，表示同一个短期会话
- `clear_history=true` 会清空该会话在 Redis 中的历史
- 返回体中的 `history_used` 表示本轮回答使用了多少条历史消息

## 5. 发起纯 LLM 对照问答

请求地址：

`POST /api/v1/chat/llm`

请求体：

```json
{
  "question": "武汉兴图新科电子股份有限公司注册资本是多少？",
  "force_refresh": true
}
```

带会话历史的 LLM 问答示例：

```json
{
  "session_id": "demo-user-llm-001",
  "question": "它的法定代表人是谁？",
  "force_refresh": true
}
```

## 6. 提交反馈

请求地址：

`POST /api/v1/feedback`

请求体：

```json
{
  "request_mode": "rag",
  "question": "武汉兴图新科电子股份有限公司注册资本是多少？",
  "answer": "武汉兴图新科电子股份有限公司注册资本为5,520万元。",
  "rating": 5,
  "comment": "答案准确"
}
```

## 7. 运行评估

请求地址：

`POST /api/v1/evaluation/run`

请求体：

```json
{
  "file_name": "招股说明书1.pdf",
  "top_k": 5,
  "questions_file": "./data/processed/evaluation_questions.json"
}
```

评估输出：

- `data/exports/ragas_eval_results.csv`
- `data/exports/ragas_eval_summary.json`
