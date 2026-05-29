# 评测报告

Date: 2026-05-19

## 评测过程

1. 确认服务已经启动在 `http://127.0.0.1:8001`。
2. 重新加载示例知识库，接口是 `POST /knowledge/reload`。
3. 创建评测用户，接口是 `POST /users`。
4. 用 `data/seed/eval_dataset.json` 跑评测脚本 `evaluation/ragas_eval.py`。
5. 评测时把“检索结果”和“回答引用”按文档/分块粒度对齐来统计。

```powershell
python evaluation/ragas_eval.py --mode all --base-url http://127.0.0.1:8001 --reload-knowledge
```

## 结果

- 检索准确率：`1.0`
- 检索召回率：`1.0`
- 回答关键词覆盖率：`0.4167`
- 回答引用准确率：`1.0`
- 回答引用召回率：`1.0`

## 说明

- 这次服务运行地址是 `http://127.0.0.1:8001`。
- 检索和引用统计已经按 chunk/document 做了对齐。
- 这份结果可以作为后续回归对比的基线。
