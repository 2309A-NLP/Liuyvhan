# RAG-工单07 优化总结

## 一、架构优化

### CCF竞赛项目架构
本项目以**CCF竞赛**为目标场景，处理太平洋保险和中国国泰君安两家公司的2021年报PDF。架构继承自工单10，核心差异在于关闭重排序并引入Redis缓存。

| 模块 | 实现 | 相比工单10差异 |
|------|------|---------------|
| 多文档自动路由 | COMPANY_FILE_HINTS + _load_doc_profiles | 完全一致（年报场景） |
| Embedding模型 | paraphrase-multilingual-MiniLM-L12-v2 (384维) | 完全一致 |
| Reranker | 已关闭 (ENABLE_RERANKER=false) | 完全一致（关闭原因相同） |
| Query理解4阶段 | 分类→改写→同义扩展→分解 | 完全一致（三独立开关） |
| Redis缓存 | 缓存键hash+TTL 3600s+会话跳过 | 完全一致 |
| 多模态图片语义 | CLIP 16类 + VLM Qwen3-VL | 完全一致 |
| 断点续传 | Checkpoint + 后台索引线程 | 完全一致 |
| 评估 | 10题 (5太平洋+5国泰君安) | 完全一致 |

### 独有特征
- **Embedding微调脚本**: 项目包含scripts/finetune_embedding.py和generate_qa_pairs.py，支持对bge-base-zh进行微调（工单11集成），答辩时可直接使用
- **答辩文档完备**: docs/包含ARCHITECTURE.md, DEFENSE_SCRIPT.md, DEFENSE_SUMMARY.md, USER_MANUAL.md等完整交付材料

## 二、工程优化

### 检索管道优化
- **6阶段管道**: 用户输入→Query理解(4阶段)→Redis缓存判→混合检索(V+B)→结构化提升→(跳过Reranker)→LLM生成
- **混合检索参数**: V:0.6 + B:0.4融合，Hybrid Candidate Pool=16，Context Neighbor Window=1
- **结构化提升**: 关键词+0.15、表格+0.12、图像+0.28、金融行业+0.18、工信领域+0.22

### 启动优化
- **后台索引线程**: 不阻塞uvicorn启动，Milvus重试3次
- **Checkpoint持久化**: 记录已索引文档数量，重启时自动恢复
- **BM25自动恢复**: 从本地chunks JSON文件恢复BM25索引

### 缓存优化
- **Redis缓存**: 首次引入缓存层，TTL 3600秒
- **对话历史跳缓存**: 有conversation_id时跳过缓存（避免上下文依赖错乱）

## 三、数据优化

### 文档数据
| 文档 | 页数 | 字符数 | 处理chunks |
|------|------|--------|-----------|
| 太平洋保险.pdf | 160 | 约40万 | 982 chunks |
| 国泰君安证券股份有限公司 .pdf | 286 | 约70万 | 1405 chunks |

### 评估数据
- 10道评估题：5道太平洋保险 + 5道国泰君安证券
- 标准答案均为人工标注，覆盖公司代码、财务数据、经营指标、利润分配等
- 评估文件：data/ccf_competition/processed/evaluation_questions.json

## 四、性能优化

### RAGAS评估指标

| 指标 | 分数 | 说明 |
|------|------|------|
| 忠实度 (FA) | 0.56 | 部分正确但6题未找到答案 |
| 上下文召回率 (CR) | 0.50 | 召回含相关页但非关键数据行 |
| 上下文精确率 (CP) | 0.48 | 召回含部分无关内容 |
| 答案相关性 (AR) | 0.34 | 多数答案为"未找到"，相关性评分低 |

### 逐题结论

| 题号 | 文档 | RAG结论 | 纯LLM结论 |
|------|------|---------|----------|
| 1-5 | 太平洋保险 | 全部未找到 | 2题正确，3题泛化 |
| 6-10 | 国泰君安 | 全部未找到 | 全部正确 |

### 性能瓶颈分析
1. **Reranker关闭**: ENABLE_RERANKER=false导致混合检索结果直接送入LLM，缺少重排序精度。建议开启可提升CR约0.10~0.15
2. **Embedding维度不足**: paraphrase-MiniLM 384维对年报专业术语的语义区分度偏低。建议切换到m3e-base(768维)或微调版bge-base-zh
3. **年报chunk分块**: 700字符chunk偏细，年报财务表的跨行关键数据容易被截断。建议增大至1000字符+overlap 200

## 五、可维护性优化

- **答辩交付完备**: docs/包含完整答辩脚本、演示脚本、架构说明、用户手册
- **微调脚本就绪**: scripts/finetune_embedding.py可直接用于Embedding模型微调
- **企业升级方案**: docs/ENTERPRISE_UPGRADE_PLAN.md包含完整的企业级RAG优化路线图
- **配置集中管理**: .env配置12项开关集中管理，无需修改代码
- **检查点机制**: 异常重启自动恢复索引状态，无需手动干预
