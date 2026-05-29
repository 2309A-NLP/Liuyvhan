# BM25 学习笔记

## 先看哪里

- [core/retriever.py](C:\Users\刘禹含\Desktop\RAG\core\retriever.py:65): 本地 BM25 + dense 的混合检索逻辑
- [database/milvus_client.py](C:\Users\刘禹含\Desktop\RAG\database\milvus_client.py:465): Milvus 原生 BM25 索引与混合检索

## 1. 本地 BM25 是怎么跑的

### 流程

1. 先按 `role_id` 取出候选文档。
2. 把 query 和每篇文档都切成 token。
3. 计算每篇文档的 BM25 分数。
4. 按分数排序，取前 `top_k`。

### 关键函数

- `_search_bm25_candidates()`：负责整条 BM25 检索链路。
- `_tokenize_for_bm25()`：把中文、英文、数字都拆成可匹配 token。
- `_bm25_score()`：真正的 BM25 打分公式。
- `_merge_hybrid_candidates()`：把 dense 分数和 BM25 分数合并。

### 你可以这样理解

BM25 本质上是“关键词匹配加权”：

- 词在当前文档里出现越多，分越高。
- 词在全库里越少见，分越高。
- 文档太长会被适当惩罚，避免长文天然占优。

## 2. Milvus 原生 BM25 是怎么跑的

### Schema

- `content_bm25`：把 `content` 字段自动映射到 `sparse`。
- `SPARSE_FLOAT_VECTOR`：BM25 生成的稀疏向量会存在这里。

### 索引

- `SPARSE_INVERTED_INDEX`：给稀疏向量建倒排索引。
- `metric_type: BM25`：告诉 Milvus 这是 BM25 语义的稀疏检索。

### 检索

- `_hybrid_search_knowledge()` 同时发起：
  - `sparse_request`：关键词/BM25 检索
  - `dense_request`：向量检索
- 然后用 `WeightedRanker(0.35, 0.65)` 融合结果。

## 3. 建议你的阅读顺序

1. 先看 [core/retriever.py](C:\Users\刘禹含\Desktop\RAG\core\retriever.py:130)
2. 再看 [core/retriever.py](C:\Users\刘禹含\Desktop\RAG\core\retriever.py:267)
3. 然后看 [database/milvus_client.py](C:\Users\刘禹含\Desktop\RAG\database\milvus_client.py:490)
4. 最后看 [database/milvus_client.py](C:\Users\刘禹含\Desktop\RAG\database\milvus_client.py:558)

## 4. 一句话总结

本地 BM25 是“自己手算分数”，Milvus BM25 是“交给数据库做稀疏检索”，两者最后都服务于混合召回。
