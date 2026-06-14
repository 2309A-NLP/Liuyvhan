# 演示视频脚本

## 演示顺序

1. 展示项目目录和 `data/raw/招股说明书1.pdf`
2. 展示 Milvus、Redis、MySQL 配置
3. 启动 FastAPI 服务
4. 在 Swagger 或 Postman 调用上传接口
5. 调用建库接口，展示页数和切块数
6. 调用 RAG 问答接口，展示答案和来源页码
7. 调用纯 LLM 接口，展示对照答案
8. 调用反馈接口
9. 调用评估接口，展示 CSV/JSON 结果
10. 打开导出的评估文件，对比 RAG vs 纯 LLM

## 推荐重点

- RAG 答案带来源页码
- 纯 LLM 不带文档约束
- RAGAS 指标与导出结果
- 通过 Redis 缓存提升重复问题速度
