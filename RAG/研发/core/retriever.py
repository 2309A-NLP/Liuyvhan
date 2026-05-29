from __future__ import annotations
"""多路召回"""
"""
======== 知识库检索  - 向量检索===========
但这个项目的知识库不是直接在 JSON 文件里现查，而是先把知识文档向量化后存进 Milvus；
Retriever 再通过 milvus_client 去 Milvus 里把相关知识块检索出来
"""
import math
import re

from models.schemas import RetrievedChunk


class Retriever:
    """知识检索器：负责把用户问题变成查询，再从向量库取回参考资料。"""

    def __init__(self, settings, milvus_client, embedding_service, rerank_service, logger):
        self.settings = settings
        self.milvus_client = milvus_client
        self.embedding_service = embedding_service
        self.rerank_service = rerank_service  # 重排序
        self.logger = logger

    """这里的 raw_results 就是前面 Milvus 混合检索已经融合过的一批候选文档。"""
    def retrieve(self, query: str, role_id: str) -> list[RetrievedChunk]:
        # 检索分三步：
        # 1. 召回候选
        # 2. 重排
        # 3. 去重和阈值过滤
        """"""
        """召回候选结果 --- 先从知识库中召回一批可能相关的原始候选知识块"""
        raw_results = self._search_candidates(query=query, role_id=role_id)
        # raw_results 列表，里面每一项是原始候选知识块字典 可能包含doc_id title  content  source  score  matched_query

        """重排序 --- 对原始召回候选做更精细的相关性重排，为后续筛选准备更高质量的排序结果。"""
        # 为什么进行重拍？？
        # 初始召回 偏‘高召回’ 会将与问题相关的内容都召回
        #但这会带来问题：
        #候选结果里可能夹杂相关性一般的内容  排序未必最优   最适合给模型的前几条，不一定排在最前面
        """把前面召回出来的候选，交给 rerank 模型重新打分排序"""
        reranked = self.rerank_service.rerank(
            query=query,
            candidates=raw_results, # 刚才召回回来的原始候选知识块列表
            top_n=max(self.settings.rerank_top_n * 2, self.settings.rerank_top_n),
        )



        """过滤结果"""
        filtered = self._filter_candidates(reranked)
        # 过滤 --- 去掉分数太低的，去掉重复内容

        return [
            RetrievedChunk(
                doc_id=item["doc_id"], # 知识块唯一编号
                title=item["title"],   # 知识块标题
                content=item["content"],  # 知识块正文内容
                source=item["source"],    # 知识来源，例如来自哪个知识文档、哪类数据源
                score=item["rerank_score"],  # 重排后的分数
            )
            for item in filtered[: self.settings.rerank_top_n] #只取最终前 N 条结果
            #self.settings.rerank_top_n 是配置里定义的最终返回数量
        ]
        # 把过滤后的字典结果，转换成标准的 RetrievedChunk 对象列表

    """召回候选 --- 
    它会把用户问题扩展成多个 query variant（查询变体）（将原始问题，改写几个近似但不同的问法），
    分别去 Milvus 检索，最后把结果合并去重，保留每个知识块最好的那次命中 得到一批候选知识块 """
    def _search_candidates(self, query: str, role_id: str) -> list[dict]:
        # 这里是检索入口：如果后端支持原生混合检索，就优先交给 Milvus。
        # 如果不支持，就在本地分别做 dense 检索和 BM25 检索，再把结果合并。
        if self.milvus_client.supports_native_hybrid and self.settings.milvus_enabled:
            return self._search_dense_candidates(query=query, role_id=role_id)
        dense_results = self._search_dense_candidates(query=query, role_id=role_id)
        bm25_results = self._search_bm25_candidates(query=query, role_id=role_id)
        return self._merge_hybrid_candidates(dense_results, bm25_results)
    #本代码完整流程
    """
    把原始问题扩展成多个查询变体
每个变体单独转向量
每个变体单独去 Milvus 检索当前角色的知识
遍历每条命中结果
按 doc_id 去重
如果同一知识块被多次命中，就保留分数最高的一次
记录这条知识块是被哪个变体召回出来的
最后返回合并后的候选列表
    """

    """
    过滤 --- 对重排结果进行 低分/去重过滤
    """
    def _filter_candidates(self, candidates: list[dict]) -> list[dict]:
        filtered: list[dict] = []
        seen_signatures: set[tuple[str, str]] = set()  # 去重空表

        for item in candidates:
            # 第一层过滤：相关度太低的候选直接丢弃。
            if item.get("rerank_score", 0.0) < self.settings.retrieval_min_score:
                # self.settings.retrieval_min_score --- 配置里的最小分数阈值
                continue
                # 跳过 不保留

            # 第二层过滤：标题和正文前部相同的内容视为重复。
            signature = (
                item.get("title", "").strip().lower(),# 标题   # strip() -- 减少格式差异  lower() -- 为了避免大小写不同但内容其实一样
                item.get("content", "").strip().lower()[:120], # 去正文【：120】 轻量
            )
            if signature in seen_signatures: # 有重复 直接去重
                continue

            seen_signatures.add(signature)  # 新知识 添加
            filtered.append(item)

        return filtered
    # 向量检索
    def _search_dense_candidates(self, query: str, role_id: str) -> list[dict]:
        merged_results: dict[str, dict] = {}

        for variant in self._build_query_variants(query):
            query_vector = self.embedding_service.embed_text(variant)
            for item in self.milvus_client.search(
                collection_name=self.settings.knowledge_collection,
                query_vector=query_vector,
                query_text=variant,
                top_k=self.settings.retrieval_top_k,
                filters={"role_id": role_id},
            ):
                best = merged_results.get(item["doc_id"])
                if best is None or item["score"] > best["score"]:
                    enriched = dict(item)
                    enriched["matched_query"] = variant
                    merged_results[item["doc_id"]] = enriched

        return list(merged_results.values())

# 本地 BM25 检索
    def _search_bm25_candidates(self, query: str, role_id: str) -> list[dict]:
        # 先把当前角色下的知识文档全部取出来，BM25 会在这些候选（原文）上做局部打分。
        corpus = self.milvus_client.list_documents(
            collection_name=self.settings.knowledge_collection,
            filters={"role_id": role_id},
        )
        if not corpus:
            return []

        # 把 query 和文档都切成 token，便于后面计算词频、文档频率和长度归一化。
        query_terms = self._tokenize_for_bm25(query)
        if not query_terms:
            return []
        document_terms = [self._tokenize_for_bm25(self._join_doc_text(doc)) for doc in corpus]
        # 对整个文档提取出title context 的集合进行分词预处理

        avgdl = sum(len(terms) for terms in document_terms) / max(len(document_terms), 1)
        #计算平均文档长度: avgdl = 平均文档长度，用来惩罚过长文档，避免长文天然占优。  作用 - 长文档的关键词权重会被降低（因为长文档更容易"碰巧"出现某个词）
        # len(terms)  --- 每天文档的长度  sum(...) - 对所有文档的 token 数量求和
        # max(len(document_terms), 1) - 文档总数，至少为 1（避免除零错误）
        # 除法 - 得到平均每篇文档有多少个 token

        doc_freq: dict[str, int] = {}  # doc_freq 记录每个词出现在多少篇文档里，后面用来算 IDF。
        for terms in document_terms:
            for term in set(terms):
                doc_freq[term] = doc_freq.get(term, 0) + 1

        scored: list[dict] = []
        total_docs = len(corpus)
        for doc, terms in zip(corpus, document_terms, strict=False): #strict=False 默认设置 两个列表长度不同时，以较短的为准，多余部分忽略 确保程序跑得动
            # 对每一篇文档计算 BM25 分数。
            score = self._bm25_score(
                query_terms=query_terms,
                document_terms=terms,
                document_frequency=doc_freq,
                total_docs=total_docs,
                avgdl=avgdl,
            )
            if score <= 0:
                continue
            item = dict(doc)         # 将原始文档 doc 转换为新字典
            item["bm25_score"] = round(score, 4)  # 给字典添加一个 "bm25_score" 键，值为 BM25 分数（四舍五入到4位小数）
            scored.append(item)

        scored.sort(key=lambda row: row["bm25_score"], reverse=True) # 将 scored 列表原地排序，按照 BM25 分数从高到低排列
        return scored[: self.settings.retrieval_top_k]

    # 合并的是：
    # dense_results：向量检索结果
    # bm25_results：本地 BM25 结果
    def _merge_hybrid_candidates(
        self,
        dense_results: list[dict],
        bm25_results: list[dict],
    ) -> list[dict]:
        merged: dict[str, dict] = {}

        # 先把 dense 和 BM25 的分数归一化，再放到同一个结果表里做融合。
        dense_max = max((item.get("score", 0.0) for item in dense_results), default=0.0)
        bm25_max = max((item.get("bm25_score", 0.0) for item in bm25_results), default=0.0)

        for item in dense_results:
            doc = dict(item)
            dense_score = float(doc.get("score", 0.0))
            doc["dense_score"] = round(dense_score, 4)
            doc["bm25_score"] = round(float(doc.get("bm25_score", 0.0)), 4)
            doc["score"] = round(dense_score / dense_max, 4) if dense_max > 0 else 0.0
            merged[doc["doc_id"]] = doc

        for item in bm25_results:
            doc_id = item["doc_id"]
            normalized_bm25 = round(float(item.get("bm25_score", 0.0)) / bm25_max, 4) if bm25_max > 0 else 0.0
            if doc_id not in merged:
                doc = dict(item)
                doc["dense_score"] = 0.0
                doc["vector_score"] = 0.0
                doc["keyword_score"] = 0.0
                doc["bm25_score"] = round(float(item.get("bm25_score", 0.0)), 4)
                doc["score"] = normalized_bm25
                doc["matched_query"] = ""
                merged[doc_id] = doc
                continue

            merged_doc = merged[doc_id]
            merged_doc["bm25_score"] = round(float(item.get("bm25_score", 0.0)), 4)
            merged_doc["score"] = round(0.65 * float(merged_doc.get("score", 0.0)) + 0.35 * normalized_bm25, 4)

        results = list(merged.values())
        results.sort(key=lambda row: row.get("score", 0.0), reverse=True)
        return results

    """生成多路查询变体"""
    def _build_query_variants(self, query: str) -> list[str]:
        normalized = self._normalize_query(query)
        variants = [normalized] if normalized else []
        if not variants:
            variants = [str(query).strip()]
        return variants[: max(1, self.settings.retrieval_query_variants)]

    """
    这三个函数 都是为了 _build_query_variants 生成query variant
    """
    # 清理格式 -
    @staticmethod
    def _normalize_query(query: str) -> str:
        query = re.sub(r"\s+", " ", str(query)).strip()
        return query.strip(" ,.;:!?，。；：！？")
    # 把查询文本做基础标准化清洗 - 1.合并多余空格  2.去掉首尾空格  3.去掉首尾多余标点

    # 去掉口头词 - 语义直接
    @staticmethod
    def _strip_filler_words(query: str) -> str:
        fillers = (
            "请问",
            "麻烦问下",
            "我想知道",
            "帮我分析一下",
            "帮我看看",
            "能不能说说",
            "可以说说",
        )
        trimmed = query
        for filler in fillers:
            if trimmed.startswith(filler): # 判断当前问题是不是以这个口头词开头
                # startswith --- Python 字符串方法
                # 字符串.startswith(前缀)  如果字符串开头就是这个前缀，返回 True 否则返回 False
                trimmed = trimmed[len(filler) :].strip()
        return trimmed

    # 提取核心词
    @staticmethod
    def _extract_focus_terms(query: str) -> list[str]:
        cleaned = "".join(ch if ch.isalnum() else " " for ch in query.lower())
        # 1.for ch in query.lower() query.lower() --- 原始问题转成小写  然后一次遍历每一个字符
        # 2.ch if ch.isalnum() else " "
        # isalnum --- 字符串方法 判断当前ch字符是否为字母或者数字  如果不是‘’替换

        terms = [term for term in cleaned.split() if len(term) >= 2]
        # 把清洗后的字符串按空格切开，并只保留长度至少为 2 的词。
        unique_terms: list[str] = []
        for term in terms:
            if term not in unique_terms:
                unique_terms.append(term)
        return unique_terms[:8]

    @staticmethod
    def _join_doc_text(doc: dict) -> str:
        return f"{doc.get('title', '')} {doc.get('content', '')}".strip()
        # 'title'   'content' 仅提取文本的标题 和 正文内容


    """
    分词/切 token
    它不是传统中文分词器，而是把文本拆成：
    英文单词
    中文单字
    中文相邻双字组 
    这是为了提高 BM25 对中英文混合文本的召回率
    """
    @staticmethod
    def _tokenize_for_bm25(text: str) -> list[str]:
        # 这里同时支持英文单词、中文单字和中文 bigram。
        # 这样既能照顾英文的词边界，也能让中文的相邻字组合有机会匹配上。
        normalized = str(text).lower()                              #  将输入文本标准化 字符串类型 英文字母转小写
        ascii_words = re.findall(r"[a-z0-9]+", normalized)  # 提取所有英文单词和数字
        cjk_chars = [ch for ch in normalized if "\u4e00" <= ch <= "\u9fff"]  #提取所有CJK（中日韩）统一表意文字字符
        cjk_bigrams = [f"{cjk_chars[i]}{cjk_chars[i + 1]}" for i in range(len(cjk_chars) - 1)]
        tokens = ascii_words + cjk_chars + cjk_bigrams  # 将三种 token 合并成一个列表
        return [token for token in tokens if token]

    @staticmethod
    def _bm25_score(
        query_terms: list[str],             # 查询分词后的词列表
        document_terms: list[str],          # 文档分词后的词列表
        document_frequency: dict[str, int], # 全局：每个词出现在多少篇文档中
        total_docs: int,                    # 总文档数 N
        avgdl: float,                       # 平均文档长度
        *,                                  # 后面的参数必须用关键字传递
        k1: float = 1.5,                    # 词频饱和度参数
        b: float = 0.75,                    # 文档长度惩罚参数
    ) -> float:                             # 返回 BM25 分数
        if not document_terms or not query_terms:  # 文档为空（没有词）/ 查询为空（没有词） 直接返回i）
            return 0.0

        # ===先统计当前文档里的词频 TF=== - 统计当前文档中每个词出现了几次（注意：这不是去重，是计数）
        # 作用 - BM25 公式中需要 词频（TF）：一个词在文档中出现次数越多，文档越相关
        term_freq: dict[str, int] = {}
        for term in document_terms:
            term_freq[term] = term_freq.get(term, 0) + 1

        doc_len = len(document_terms)
        score = 0.0
        for term in query_terms:  # 遍历查询中的每个词出现次数 # 注意：没有去重！
            freq = term_freq.get(term, 0)
            if freq == 0:
                continue

            # ===IDF(逆文档频率)===
            df = document_frequency.get(term, 0)
            # IDF：越稀有的词越重要。
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            # BM25 核心权重：词频越高分越高，但文档越长会被适当惩罚。
            numerator = freq * (k1 + 1)
            denominator = freq + k1 * (1 - b + b * doc_len / max(avgdl, 1e-6))
            score += idf * numerator / denominator
        return score

    """
    staticmethod -- 静态方法
    这是不依赖对象内部配置、只做纯文本处理的小工具函数
    内部配置例如：
    self.settings
    self.milvus_client
    self.embedding_service
    
    """
