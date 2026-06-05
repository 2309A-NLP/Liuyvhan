# 用户手册

## 1. 准备数据

把 `招股说明书1.pdf` 放到以下目录：

`data/raw/`

也可以通过接口上传：

- `POST /api/v1/documents/upload`

## 2. 构建向量索引

请求地址：

`POST /api/v1/documents/index`

请求体：

```json
{
  "file_name": "招股说明书1.pdf",
  "rebuild": true
}
```

## 3. 发起 RAG 问答

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
- `sources`：命中的来源片段
- `page`：来源页码
- `score`：相似度

## 4. 发起纯 LLM 对照问答

请求地址：

`POST /api/v1/chat/llm`

请求体：

```json
{
  "question": "武汉兴图新科电子股份有限公司注册资本是多少？",
  "force_refresh": true
}
```

## 5. 提交反馈

请求地址：

`POST /api/v1/feedback`

请求体：

```json
{
  "request_mode": "rag",
  "question": "武汉兴图新科电子股份有限公司注册资本是多少？",
  "answer": "注册资本为5,520万元。",
  "rating": 5,
  "comment": "答案准确"
}
```

## 6. 运行评估

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

评估结果会输出到：

- `data/exports/ragas_eval_results.csv`
- `data/exports/ragas_eval_summary.json`
