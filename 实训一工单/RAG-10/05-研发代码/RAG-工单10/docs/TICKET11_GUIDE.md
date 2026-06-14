# Embedding 模型微调任务操作指南

工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务  
日期：2025年8月  
负责人：王洪荣

---

## 概览

任务目标：在金融招股说明书数据上微调 Embedding 模型，提升 RAG 系统的检索准确性。

### 数据流

```
原始PDF ──→ 3511个chunk ──→ LLM生成问答对(200+条) ──→ 三元组(500+条)
                                      ↓
                               微调 bge-base-zh-v1.5
                                      ↓
                             微调后的 Embedding 模型
                                      ↓
                             替换原m3e-base → 重新索引 → RAGAS评估对比
```

---

## 操作步骤

### 第1步：生成训练数据

双击运行 `scripts/run_generate_data.bat`  
或在 Anaconda Prompt 中执行：

```bash
cd D:\Users\刘禹含\Desktop\RAG-工单04
D:\Anaconda\envs\RAG\python.exe scripts\generate_qa_pairs.py --limit 200
```

**说明：**
- 脚本会读取 `data/processed/*_chunks.json` 中的全部 chunk
- 调用 SiliconFlow 的 DeepSeek-V4-Flash 为每个 chunk 生成问答对
- 自动过滤太短的 chunk，按页均匀采样
- 在 `evaluation_questions.json` 的14个人工标注数据基础上，生成约200条合成问答对
- 最终通过 hard negative mining 构造 500+ 条三元组

**耗时预估：** 5-10 分钟（取决于 API 响应速度）

**输出文件：**
- `data/processed/qa_pairs_generated.json` — 生成的问答对
- `data/processed/qa_pairs_merged.json` — 合并去重后的问答对
- `data/processed/finetune_triplets.json` — 最终三元组训练数据

---

### 第2步：微调模型

双击运行 `scripts/run_finetune.bat`  
或在 Anaconda Prompt 中执行：

```bash
cd D:\Users\刘禹含\Desktop\RAG-工单04
D:\Anaconda\envs\RAG\python.exe scripts\finetune_embedding.py --epochs 3 --batch-size 8
```

**说明：**
- 下载 BAAI/bge-base-zh-v1.5 作为基准模型（768维，中文优化）
- 使用 TripletLoss 在三元组数据上训练 3 个 epoch
- CPU 模式运行，500+ 条三元组约 20-30 分钟

**可选参数：**
- `--epochs 5` — 增加训练轮数（数据少的情况下可能过拟合）
- `--batch-size 16` — 增大批次（CPU 可能 OOM，建议8）
- `--lr 3e-5` — 调大学习率
- `--test-only` — 先测试数据格式是否正确，不训练

**输出：**
- `data/models/finetuned-bge-zh/` — 微调后的模型权重
- `data/exports/finetune_report.txt` — 训练报告
- `data/exports/finetune_loss_curve.png` — 损失曲线（需 matplotlib）

---

### 第3步：评估对比

#### 3.1 先跑微调前基线

确保 .env 中 `EMBEDDING_MODEL_PATH` 还是指向原 m3e-base 模型，然后：

```bash
cd D:\Users\刘禹含\Desktop\RAG-工单04
D:\Anaconda\envs\RAG\python.exe scripts\run_eval_comparison.py --baseline
```

**输出：** `data/exports/eval_baseline/` 目录

#### 3.2 部署微调后模型

1. 修改 `.env`：
   ```
   EMBEDDING_MODEL_PATH=data/models/finetuned-bge-zh/
   ```
2. 重启服务（双击 `restart.bat` 或 `start_server_loop.bat`）
3. 重新索引 PDF（调用 API `/api/v1/ingest` 或重新启动后自动触发）

#### 3.3 跑微调后评估

```bash
cd D:\Users\刘禹含\Desktop\RAG-工单04
D:\Anaconda\envs\RAG\python.exe scripts\run_eval_comparison.py --after
```

系统会自动生成对比报告 `data/exports/eval_comparison.md`

---

## 验收标准

| 指标 | 说明 | 验收条件 |
|------|------|---------|
| context_recall | 上下文召回率 | 微调后 > 微调前 |
| context_precision | 上下文精确率 | 微调后 > 微调前 |
| faithfulness | 忠实度 | 微调后 >= 微调前 |
| answer_relevancy | 答案相关性 | 微调后 >= 微调前 |

50% 以上的指标提升即视为通过验收。

---

## 产出物清单

- [ ] 训练数据集 `data/processed/finetune_triplets.json`
- [ ] 微调后模型 `data/models/finetuned-bge-zh/`
- [ ] 训练报告 `data/exports/finetune_report.txt`
- [ ] 微调前评估结果 `data/exports/eval_baseline/`
- [ ] 微调后评估结果 `data/exports/eval_after_finetune/`
- [ ] 对比报告 `data/exports/eval_comparison.md`

---

## 常见问题

**Q: 下载 bge-base-zh-v1.5 太慢怎么办？**  
A: 可以在 Windows 上先开代理下载，或者手动从 HuggingFace 下载后放到本地路径。

**Q: CPU 训练太慢怎么办？**  
A: 500条三元组在 CPU 上 3 个 epoch 约 20-30 分钟，可以接受。如果特别慢，可以减小 `--batch-size 4`。

**Q: 微调后效果反而变差了？**  
A: 可能原因：1) 三元组数据质量不够好 2) epoch 太多过拟合 3) 学习率不合适。建议先用 `--epochs 2` 试试。

**Q: 需要 GPU 吗？**  
A: 不需要。bge-base-zh-v1.5 只有 110M 参数，CPU 上 500 条数据 3 个 epoch 完全跑得动。
