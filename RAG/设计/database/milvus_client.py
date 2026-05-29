from __future__ import annotations
"""
存知识和长期记忆 -- 混合检索
"""
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

"""
对上层暴露统一接口的门面类
作用：
给上层提供统一接口
屏蔽“远程 Milvus / 本地文件”差异
"""
class MilvusClient:
    """向量库网关。

    对上层暴露统一的 upsert/search 接口，屏蔽“真 Milvus / 本地文件”
    两套实现差异。
    """

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self._backend = self._build_backend() # 决定当前到底用远程 Milvus 还是本地文件后端
        self.storage_mode = self._backend.storage_mode
        self.supports_native_hybrid = getattr(self._backend, "supports_native_hybrid", False)


    def ensure_collection(self, collection_name: str) -> None:
        self._backend.ensure_collection(collection_name)
        # 确保某个 collection 存在

    def count(self, collection_name: str) -> int:
        return self._backend.count(collection_name)
        # 统计某个 collection 里有多少条数据

    def reset_collection(self, collection_name: str) -> None:
        self._backend.reset_collection(collection_name)
        # 重置某个 collection，清空并重建

    def upsert_documents(self, collection_name: str, documents: list[dict[str, Any]]) -> int:
        return self._backend.upsert_documents(collection_name, documents)
        # 往某个 collection 里插入/更新文档

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        query_text: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self._backend.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_text=query_text,
            top_k=top_k,
            filters=filters,
        )

    def list_documents(
        self,
        collection_name: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._backend.list_documents(
            collection_name=collection_name,
            filters=filters,
            limit=limit,
        )

    # 这是混合检索的关键入口
    # 上层调用它时，会把：
    # 向量查询 query_vector
    # 文本查询 query_text
    # 过滤条件 filters
    # 一起传进来


    def _build_backend(self):               # 先尝试构建远程 Milvus 后端  如果失败，就降级成 _LocalMilvusBackend

        # 优先尝试真实 Milvus，连不上时自动降级到本地文件模式。
        if self.settings.milvus_enabled:
            try:
                backend = _RemoteMilvusBackend(self.settings, self.logger)
                self.logger.info("Milvus backend=remote uri=%s", self.settings.milvus_uri)
                return backend
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "Failed to initialize remote Milvus at %s, falling back to local file store. reason=%s",
                    self.settings.milvus_uri,
                    exc,
                )

        self.logger.info("Milvus backend=local-file path=%s", self.settings.local_milvus_path)
        return _LocalMilvusBackend(self.settings, self.logger)


"""
本地文件版后端，做降级存储和本地混合检索
特点：
数据存到本地 JSON 文件
自己在 Python 里模拟“混合检索”
很适合本地教学、兜底运行
"""
class _LocalMilvusBackend:
    storage_mode = "local-file"
    supports_native_hybrid = False

    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.storage_path: Path = settings.local_milvus_path
        self._store = self._load_store()

    def _load_store(self) -> dict[str, list[dict[str, Any]]]:
        if not self.storage_path.exists():
            return {}
        return json.loads(self.storage_path.read_text(encoding="utf-8"))
    # 从本地 JSON 文件读出所有 collection 数据

    def _flush(self) -> None:
        self.storage_path.write_text(
            json.dumps(self._store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    # 把当前内存中的数据写回本地 JSON 文件


    def ensure_collection(self, collection_name: str) -> None:
        created = collection_name not in self._store
        self._store.setdefault(collection_name, [])
        self._flush()
        action = "created" if created else "loaded"
        self.logger.info(
            "Milvus(local-file) collection_%s name=%s path=%s",
            action,
            collection_name,
            self.storage_path,
        )
    # 作用 ---
    # 确保本地存储里有这个 collection
    # 如果没有，就创建一个空列表

    def count(self, collection_name: str) -> int:
        return len(self._store.get(collection_name, []))
    # 统计本地该 collection 里有多少条文档

    def reset_collection(self, collection_name: str) -> None:
        self._store[collection_name] = []
        self._flush()
        self.logger.info(
            "Milvus(local-file) collection_reset name=%s path=%s",
            collection_name,
            self.storage_path,
        )
        # 清空该 collection

    def upsert_documents(self, collection_name: str, documents: list[dict[str, Any]]) -> int:
        existing = {item["doc_id"]: item for item in self._store.setdefault(collection_name, [])}
        for doc in documents:
            existing[doc["doc_id"]] = doc
        self._store[collection_name] = list(existing.values())
        self._flush()
        self.logger.info(
            "Milvus(local-file) documents_upserted collection=%s count=%s total=%s",
            collection_name,
            len(documents),
            len(self._store[collection_name]),
        )
        return len(documents)
        # 用 doc_id 做 key，插入或覆盖文档
        # 然后写回文件

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        query_text: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        # 本地降级模式下，自己手工做一次“向量分 + 关键词分”的混合检索。
        filters = filters or {}
        candidates: list[dict[str, Any]] = []
        for doc in self._store.get(collection_name, []):
            if not _match_filters(doc, filters):
                continue
            vector_score = _cosine(query_vector, np.array(doc["vector"], dtype=float))
            keyword_score = _keyword_score(query_text, doc["content"])
            hybrid_score = 0.7 * vector_score + 0.3 * keyword_score
            doc_copy = dict(doc)
            doc_copy["vector_score"] = round(vector_score, 4)
            doc_copy["keyword_score"] = round(keyword_score, 4)
            doc_copy["score"] = round(hybrid_score, 4)
            candidates.append(doc_copy)
        candidates.sort(key=lambda item: item["score"], reverse=True)
        results = candidates[:top_k]
        self.logger.info(
            "Milvus(local-file) search collection=%s top_k=%s filters=%s hits=%s query=%s",
            collection_name,
            top_k,
            filters,
            len(results),
            _clip_log_text(query_text),
        )
        return results

    def list_documents(
        self,
        collection_name: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        documents = [
            dict(doc)
            for doc in self._store.get(collection_name, [])
            if _match_filters(doc, filters)
        ]
        if limit is not None:
            documents = documents[:limit]
        self.logger.info(
            "Milvus(local-file) list_documents collection=%s filters=%s total=%s",
            collection_name,
            filters,
            len(documents),
        )
        return documents
    #本地模式下的混合检索核心
    # 对每条候选文档：
    # 先按 filters 过滤
    # 算向量分 vector_score
    # 算关键词分 keyword_score
    # 合成混合分：

"""
真正连接 Milvus 的远程后端
"""
class _RemoteMilvusBackend:
    # 下面两个是类属性，表示这个后端的能力标签
    storage_mode = "milvus"         # 表示当前存储模式是真正的 Milvus，而不是本地 JSON 兜底版
    supports_native_hybrid = True  #表示这个后端支持 Milvus 原生混合检索，也就是可以直接做 dense + sparse/BM25 的 hybrid search


    """先导入 pymilvus，再连接 Milvus，顺便把各种 Milvus 类对象保存起来"""
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger =logger
        self.alias = f"rag_role_studio_{id(self)}"
        # 它是在给 “Milvus 连接”本身起名字
        # 为什么连接还需要名字？？？？
        # 因为 pymilvus 的连接管理不是“你连了就完事”，而是它内部会维护一个连接池/连接注册表。
        # 你每建立一条连接，Milvus Python SDK 都要知道：
        # 这条连接以后怎么被引用？？？？
        # 很多库默认只维护一条连接，这样你不需要起名字。
        # 但 pymilvus 支持多连接，所以它必须有办法区分：
        # 连接到本地开发环境的 Milvus  ----- Milvus 跑在你自己电脑上
        # 连接到测试环境的 Milvus     ----- Milvus 跑在一台专门给测试用的服务器上 作用-给开发人员联调   给测试人员验证功能  模拟比较接近真实部署的环境 先试新代码，确认没问题再上线
        # 连接到生产环境的 Milvus     ----- 真正在线上给真实用户服务的 Milvus
        # 甚至同一个进程里可以同时连多个 Milvus 地址
        self._collections: dict[str, Any] = {}

        # 定义pymilvus包
        try:
            from pymilvus import (  # 导入 pymilvus 工具
                AnnSearchRequest,  # 混合检索请求对象
                Collection,        # 用来操作 collection（表）
                CollectionSchema,  # 定义表结构
                DataType,          # 定义字段
                FieldSchema,       # 定义 BM25 function
                Function,
                FunctionType,
                WeightedRanker,   # 混合检索结果加权融合
                connections,      # 负责连接 Milvus
                utility,          # 一些管理工具，比如判断 collection 是否存在
            )
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError("pymilvus is not installed.") from exc

        # 把刚才导入的工具，保存成这个对象自己的属性
        self.AnnSearchRequest = AnnSearchRequest
        self.Collection = Collection             # 整张表
        # Collection --- 详细介绍
        # 定义 - Milvus 里的“一张表 / 一个数据集合  作用 - 把要检索的文档数据存起来，并支持后续查找
        # 作用 1.存数据    doc_id  title  content role_id  vector sparse
        #     2.建索引     vector 建向量索引
        #                 sparse 建 BM25 索引
        #     3.做检索     在collection做向量检索  BM25 检索  混合检索
        # 在你项目里常见的 collection 有：
        # role_knowledge
        # 作用：存角色知识库，给 RAG 检索用
        # user_long_memory
        # 作用：存用户长期记忆

        self.CollectionSchema = CollectionSchema # 把多个字段合起来，组成整张表的结构
        self.DataType = DataType
        self.FieldSchema = FieldSchema           # 定义表里的某一个字段
        self.Function = Function
        self.FunctionType = FunctionType
        self.WeightedRanker = WeightedRanker
        self.connections = connections
        self.utility = utility

        connect_kwargs: dict[str, Any] = {"alias": self.alias, "uri": self.settings.milvus_uri} # 这一步是在准备一个“连接 Milvus 要用的参数字典
        # alias -- 这条连接的名字
        # uri --- Milvus 的地址  env 里的： http://127.0.0.1:19530
        # 待会儿我要用这个连接名，去连接这个 Milvus 地址
        if getattr(self.settings, "milvus_token", ""): #看你的 settings 配置对象里，milvus_token 这个值是不是空的  不是空的说明连接 Milvus 时要把这个认证信息带上
        #milvus_token -- 连接 Milvus 时可能需要的认证凭证  如果有加进去
            connect_kwargs["token"] = self.settings.milvus_token
        self.connections.connect(**connect_kwargs) # 真正链接milvus
        self.logger.info(
            "Milvus(remote) connection_ready uri=%s alias=%s",
            self.settings.milvus_uri,
            self.alias,
        )
    """确保某个 collection 存在。
    如果 schema 变了，就删掉重建；如果不存在，就创建并加载"""
    def ensure_collection(self, collection_name: str) -> None:

        # 检查是否存在collection 并 检查是否过时
        if self.utility.has_collection(collection_name, using=self.alias):
            # collection_name --- collection 名字
            # using=self.alias：指定用哪条 Milvus 连接去查

            collection = self._get_collection(collection_name) # 获取collection 对象

            if self._schema_upgrade_required(collection_name, collection):
                # _schema_upgrade_required函数作用 --检查collection 是否过时
                collection.drop()  # 把 Milvus 里的这个 collection 直接删除。
                self._collections.pop(collection_name, None) # 把 Python 内存里缓存的这个 collection 对象也删掉。因为表都没了，缓存对象也不能留着。
                self.logger.info("Milvus(remote) collection_dropped_for_schema_upgrade name=%s", collection_name)
                # 记录一条日志，说明这次删除不是意外，而是为了 schema 升级

        # 检查是否存在collection
        if not self.utility.has_collection(collection_name, using=self.alias):# 第一块：如果 collection 不存在，就创建
            schema = self._build_collection_schema(collection_name)           #先生成 schema 这里是在生成这张 collection 的结构定义
            collection = self.Collection(name=collection_name, schema=schema, using=self.alias) # 真正创建 collection
            self._ensure_collection_indexes(collection_name, collection)
            collection.load()
            self._collections[collection_name] = collection
            self.logger.info(
                "Milvus(remote) collection_created name=%s dim=%s",
                collection_name,
                self.settings.embedding_dimension,
            )
            return

        # 如果 collection 已存在，就直接加载并确保可用
        collection = self._get_collection(collection_name)
        self._ensure_collection_indexes(collection_name, collection)
        collection.load()
        self.logger.info(
            "Milvus(remote) collection_loaded name=%s entities=%s",
            collection_name,
            int(collection.num_entities),
        )

    def count(self, collection_name: str) -> int:
        collection = self._get_collection(collection_name)
        return int(collection.num_entities)

    def reset_collection(self, collection_name: str) -> None:
        if self.utility.has_collection(collection_name, using=self.alias):
            collection = self._get_collection(collection_name)
            collection.drop()
            self._collections.pop(collection_name, None)
            self.logger.info("Milvus(remote) collection_dropped name=%s", collection_name)
        self.ensure_collection(collection_name)


    """把文档写进 Milvus 前先做标准化，然后批量插入/更新"""
    def upsert_documents(self, collection_name: str, documents: list[dict[str, Any]]) -> int:
        if not documents:
            return 0

        collection = self._get_collection(collection_name) #
        payload = [self._normalize_document(collection_name, item) for item in documents]
        collection.upsert(payload)
        collection.flush()
        self.logger.info(
            "Milvus(remote) documents_upserted collection=%s count=%s",
            collection_name,
            len(payload),
        )
        return len(payload)


    """混合检索核心代码"""
    """这是最关键的入口。

如果是 knowledge_collection，走 _hybrid_search_knowledge()，也就是 BM25 + 向量的原生混合检索。
如果不是，就走普通向量检索，再手动加关键词分数。"""
    # 定义一个检索函数
    def search(
        self,
        collection_name: str,  # 定义要查哪个 Milvus 集合，比如知识库集合、长期记忆集合
        query_vector: np.ndarray,
        query_text: str,       # 原始文本 -- 做关键词打分
        top_k: int,            # 这次要召回前多少条候选结果
        filters: dict[str, Any] | None = None,  # 过滤条件，比如 role_id、user_id。作用是限制只在某一类数据里查，不是全库乱搜
    ) -> list[dict[str, Any]]: # 返回的是“字典列表 --- 这是一个列表，列表里的每一个元素都是字典；这个字典的 key 是字符串，value 可以是任意类型
        if collection_name == self.settings.knowledge_collection:
            return self._hybrid_search_knowledge(
                collection_name=collection_name,
                query_vector=query_vector,
                query_text=query_text,
                top_k=top_k,
                filters=filters,
            )

        collection = self._get_collection(collection_name)  # 确定检索内容为 长期记忆  或 知识库 向量表
        expr = self._build_filter_expr(filters or {})       # 过滤条件转成 Milvus 能识别的查询表达式 - 告诉 Milvus，只在满足条件的数据范围里做向量检索
        #{"role_id": "therapist"} 转换成 role_id == "therapist"

        # 第一步：先让 Milvus 按向量相似度召回 doc_id。
        search_result = collection.search(
            data=[query_vector.tolist()], # 传入查询向量
            # 为什么要用 .tolist()
            # query_vector 现在是 numpy.ndarray  Milvus 接口更适合接收普通 Python list

            anns_field="vector", # 和文档中向量部分 进行比较
            param={"metric_type": "IP", "params": {}},
            # Milvus 用内积 IP 来计算 query_vector 和库里每条文档 vector 的相似度分数。
            # 类似{
            #     "doc_001": 0.91,
            #     "doc_002": 0.87,
            #     "doc_003": 0.82,
            # }
            limit=top_k,
            expr=expr,
            output_fields=["doc_id"],# 只召回 doc_id
        )
        hits = search_result[0] if search_result else [] # 取出  doc_id -> 相似度分数
        if not hits:
            return []

        distances: dict[str, float] = {}
        for hit in hits:
            doc_id = str(getattr(hit, "id", "")) # 从命中结果his 里面取出doc_id
            if not doc_id:
                continue
            distances[doc_id] = float(getattr(hit, "distance", 0.0))

        if not distances:
            return []

        # 第二步：再根据 doc_id 把文本字段查回来，方便后续重排和展示引用内容。
        # 根据第一步向量召回出来的 doc_id，把完整文档内容查回来，再结合向量分数和关键词分数做混合打分，最后按最终分数排序并返回结果
        query_result = collection.query(
            expr=f"doc_id in {json.dumps(list(distances.keys()), ensure_ascii=False)}",
            output_fields=["doc_id", "title", "content", "source", "role_id", "user_id"],
        )
        # 按 doc_id 回查完整文档

        candidates: list[dict[str, Any]] = []
        for doc in query_result:
            doc_id = str(doc.get("doc_id", ""))
            if not doc_id:
                continue
            vector_score = max(float(distances.get(doc_id, 0.0)), 0.0)   # 第一轮 Milvus 向量召回得到的分数
            keyword_score = _keyword_score(query_text, str(doc.get("content", ""))) # 当前查询文本和文档正文的关键词匹配分数
            hybrid_score = 0.7 * vector_score + 0.3 * keyword_score             # 最终融合分数
            doc_copy = dict(doc)

            doc_copy["vector_score"] = round(vector_score, 4)
            doc_copy["keyword_score"] = round(keyword_score, 4)
            doc_copy["score"] = round(hybrid_score, 4)
            # 把打分结果塞回候选文档  --- 给每个候选文档补充评分信息，方便后面排序和返回
            candidates.append(doc_copy)  # 把当前已经完成混合打分的文档结果加入候选列表

        candidates.sort(key=lambda item: item["score"], reverse=True) # 比分倒叙排序
        results = candidates[:top_k]  #只保留前 top_k 条
        self.logger.info(
            "Milvus(remote) search collection=%s top_k=%s filters=%s hits=%s query=%s",
            collection_name,
            top_k,
            filters or {},
            len(results),
            _clip_log_text(query_text),
        )
        return results

    """按过滤条件把文档原文查出来，给 BM25 计算或展示用"""
    def list_documents(
        self,
        collection_name: str,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        collection = self._get_collection(collection_name)
        expr = self._build_filter_expr(filters or {}) or 'doc_id != ""'
        documents = collection.query(
            expr=expr,
            output_fields=["doc_id", "title", "content", "source", "role_id", "user_id"],
        )
        if limit is not None:
            documents = documents[:limit]
        self.logger.info(
            "Milvus(remote) list_documents collection=%s filters=%s total=%s",
            collection_name,
            filters or {},
            len(documents),
        )
        return [dict(item) for item in documents]

    """定义 Milvus 里这张表长什么样。
知识库会多一个 sparse 字段和 content_bm25 函数，用来支持 BM25"""
    def _build_collection_schema(self, collection_name: str):
        if collection_name == self.settings.knowledge_collection:
            # knowledge collection 同时保留 dense 向量和 sparse 向量。
            # sparse 向量会由 BM25 自动生成，用于关键词检索。
            return self.CollectionSchema(
                fields=[
                    self.FieldSchema(
                        name="doc_id",
                        dtype=self.DataType.VARCHAR,
                        is_primary=True,
                        auto_id=False,
                        max_length=256,
                    ),
                    self.FieldSchema(name="title", dtype=self.DataType.VARCHAR, max_length=512),
                    self.FieldSchema(name="content", dtype=self.DataType.VARCHAR, max_length=8192, enable_analyzer=True),
                    self.FieldSchema(name="source", dtype=self.DataType.VARCHAR, max_length=256),
                    self.FieldSchema(name="role_id", dtype=self.DataType.VARCHAR, max_length=128),
                    self.FieldSchema(name="user_id", dtype=self.DataType.VARCHAR, max_length=128),
                    self.FieldSchema(name="sparse", dtype=self.DataType.SPARSE_FLOAT_VECTOR),
                    self.FieldSchema(
                        name="vector",
                        dtype=self.DataType.FLOAT_VECTOR,
                        dim=self.settings.embedding_dimension,
                    ),
                ],
                functions=[
                    self.Function(
                        name="content_bm25",
                        # 把 content 字段交给 Milvus 的 BM25 函数生成 sparse 向量。
                        function_type=self.FunctionType.BM25,
                        input_field_names=["content"],
                        output_field_names=["sparse"],
                    )
                ],
                description=f"RAG Role Studio collection: {collection_name}",
                enable_dynamic_field=True,
            )

        return self.CollectionSchema(
            fields=[
                self.FieldSchema(
                    name="doc_id",
                    dtype=self.DataType.VARCHAR,
                    is_primary=True,
                    auto_id=False,
                    max_length=256,
                ),
                self.FieldSchema(name="title", dtype=self.DataType.VARCHAR, max_length=512),
                self.FieldSchema(name="content", dtype=self.DataType.VARCHAR, max_length=8192),
                self.FieldSchema(name="source", dtype=self.DataType.VARCHAR, max_length=256),
                self.FieldSchema(name="role_id", dtype=self.DataType.VARCHAR, max_length=128),
                self.FieldSchema(name="user_id", dtype=self.DataType.VARCHAR, max_length=128),
                self.FieldSchema(
                    name="vector",
                    dtype=self.DataType.FLOAT_VECTOR,
                    dim=self.settings.embedding_dimension,
                ),
            ],
            description=f"RAG Role Studio collection: {collection_name}",
            enable_dynamic_field=True,
        )

    def _knowledge_schema_upgrade_required(self, collection) -> bool:
        field_names = {field.name for field in collection.schema.fields}
        if "sparse" not in field_names:
            return True
        return self._collection_vector_dim(collection) != self.settings.embedding_dimension


    """判断collection 格式是否过时"""
    # 当前 collection 的结构，是否仍然满足现在代码对“字段能力”和“向量维度”的要求。例如以前配置EMBEDDING_DIMENSION=512  后来改成：
    # EMBEDDING_DIMENSION=768  如果那老 collection 里的 vector 字段还是 512 维  这时候这个函数也会返回 True，因为 旧表的向量维度已经不适配新的 embedding 模型了
    # 知识库表：检查 sparse + 维度
    # 普通表：检查 维度
    # 如果不满足，就说明 schema 过时，需要升级
    def _schema_upgrade_required(self, collection_name: str, collection) -> bool: # 布尔值返回 True：需要升级 schema，说明结构过时了
        if collection_name == self.settings.knowledge_collection: #第一层判断：是不是知识库表 role_knowledge 比普通 collection 更复杂它不仅有vector 还多了 sparse还依赖 BM25 function 所以它的 schema 检查标准更严格，不能只看向量维度。
            return self._knowledge_schema_upgrade_required(collection) #如果是知识库表，就走专门检查
        return self._collection_vector_dim(collection) != self.settings.embedding_dimension  #  如果不是知识库表，就只检查向量维度

    """第二步：筛选表做索引"""
    def _ensure_collection_indexes(self, collection_name: str, collection) -> None:
        if collection_name == self.settings.knowledge_collection:# 判断是知识库表（vector 的向量索引 sparse 的 BM25 倒排索引 ）
            self._ensure_knowledge_indexes(collection) # 知识库专用索引逻辑
            return
        self._ensure_vector_index(collection)          # 只管普通向量索引

    """第一步：筛选表做  索引：为了让后续检索更快、更能正常工作，提前给某个字段建立的检索结构"""
    """给 vector 建向量索引，给 sparse 建 BM25 倒排索引"""
    def _ensure_knowledge_indexes(self, collection) -> None:
        existing_fields = {index.field_name for index in getattr(collection, "indexes", [])} # 先看这张表已经给哪些字段建过索引了，避免重复建
        if "vector" not in existing_fields:  # 这里是在给 vector 字段建索引
            collection.create_index(
                field_name="vector",         # 表示针对向量字段建索引
                index_params={"index_type": "AUTOINDEX", "metric_type": "IP", "params": {}},
                # index_type="AUTOINDEX" --- 意思是让 Milvus 自动选择/管理比较合适的向量索引方式 向量索引的自动模式
                # metric_type="IP" IP = Inner Product，内积相似度
                # 在你的项目里，这表示向量检索时用内积来比较 query 向量和文档向量的相似度

            )
        if "sparse" not in existing_fields:
            collection.create_index(
                field_name="sparse",
                # sparse 字段使用倒排索引 + BM25 语义，专门服务关键词检索。
                index_params={
                    "index_type": "SPARSE_INVERTED_INDEX",
                    "metric_type": "BM25",
                    "params": {"inverted_index_algo": "DAAT_MAXSCORE"},
                },
            )

    """同时发两路检索：
sparse_request = BM25 关键词检索
dense_request = 向量语义检索
然后用 WeightedRanker(0.35, 0.65) 融合。"""
    def _hybrid_search_knowledge(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        query_text: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        collection = self._get_collection(collection_name) # 拿到当前知识库表的操作对象
        expr = self._build_filter_expr(filters or {}) or None # 把过滤条件转成 Milvus 查询表达式
        # 两路检索都只会在当前角色的知识块里查

        # sparse_request = 关键词/BM25 检索
        sparse_request = self.AnnSearchRequest(
            data=[query_text], #问题原文 (经过 Milvus 的 BM25 function自动生成的稀疏表示)
            anns_field="sparse", # 表示这一路检索要查的是文档的 sparse 字段
            param={"params": {}},
            limit=top_k,
            expr=expr,
        )
        # dense_request = 向量语义检索
        dense_request = self.AnnSearchRequest(
            data=[query_vector.tolist()],
            anns_field="vector",
            param={"metric_type": "IP", "params": {}}, # 表示用内积作为相似度度量
            limit=top_k,
            expr=expr,
        )
        search_result = collection.hybrid_search(
            reqs=[sparse_request, dense_request],
            # 这里把 sparse 和 dense 的结果按权重融合。
            rerank=self.WeightedRanker(0.35, 0.65),
            limit=top_k,
            output_fields=["doc_id", "title", "content", "source", "role_id", "user_id"],
        )
        hits = search_result[0] if search_result else []
        results: list[dict[str, Any]] = []
        for hit in hits:
            entity = hit.entity
            results.append(
                {
                    "doc_id": str(getattr(hit, "id", entity.get("doc_id", ""))),
                    "title": entity.get("title", ""),
                    "content": entity.get("content", ""),
                    "source": entity.get("source", ""),
                    "role_id": entity.get("role_id", ""),
                    "user_id": entity.get("user_id", ""),
                    "score": round(float(getattr(hit, "distance", 0.0)), 4),
                    "vector_score": round(float(getattr(hit, "distance", 0.0)), 4),
                    "keyword_score": 0.0,
                }
            )
        self.logger.info(
            "Milvus(remote) hybrid_search collection=%s top_k=%s filters=%s hits=%s query=%s",
            collection_name,
            top_k,
            filters or {},
            len(results),
            _clip_log_text(query_text),
        )
        return results

    """
    作用 -- 缓存 collection 对象
    """
    def _get_collection(self, collection_name: str):
        if collection_name not in self._collections:
            self._collections[collection_name] = self.Collection(name=collection_name, using=self.alias)
            # self.Collection(name=collection_name, using=self.alias) --- 真正创建 Milvus 的集合操作对象
            # name=collection_name --- 链接集合名称
            # using=self.alias --- 用哪个 Milvus 连接别名
        return self._collections[collection_name]

    """检查向量维度"""
    @staticmethod
    def _collection_vector_dim(collection) -> int | None:
        for field in getattr(collection.schema, "fields", []):
            if getattr(field, "name", "") == "vector":
                params = getattr(field, "params", {}) or {}
                try:
                    return int(params.get("dim", 0) or 0)
                except (TypeError, ValueError):
                    return None
        return None


    def _ensure_vector_index(self, collection) -> None:
        if getattr(collection, "indexes", None):
            return
        try:
            collection.create_index(
                field_name="vector",
                index_params={"index_type": "AUTOINDEX", "metric_type": "IP", "params": {}},
            )
        except Exception:  # noqa: BLE001
            collection.create_index(
                field_name="vector",
                index_params={"index_type": "HNSW", "metric_type": "IP", "params": {"M": 8, "efConstruction": 64}},
            )
    """补齐字段、转换向量格式"""
    def _normalize_document(self, collection_name: str, document: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(document)
        normalized.setdefault("title", "")
        normalized.setdefault("content", "")
        normalized.setdefault("source", "")
        normalized.setdefault("role_id", "")
        normalized.setdefault("user_id", "")
        normalized["vector"] = self._normalize_vector(normalized.get("vector"))
        if collection_name == self.settings.knowledge_collection:
            normalized.pop("sparse", None)
        return normalized

    @staticmethod
    def _normalize_vector(vector: Any) -> list[float]:
        if isinstance(vector, np.ndarray):
            return vector.astype("float32").tolist()
        return [float(item) for item in vector]

    """把过滤条件拼成 Milvus 查询语句"""
    @staticmethod
    def _build_filter_expr(filters: dict[str, Any]) -> str:
        clauses: list[str] = []
        for key, value in filters.items():
            if value in (None, ""):
                continue
            clauses.append(f"{key} == {json.dumps(value, ensure_ascii=False)}")
        return " and ".join(clauses)


def _match_filters(doc: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, value in filters.items():
        if doc.get(key) != value:
            return False
    return True


"""看向量分怎么计算"""
def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    if denominator == 0:
        return 0.0
    return float(np.dot(left, right) / denominator)

"""看关键词分怎么计算"""
# 把查询文本和文档内容都拆成词，再看它们有多少关键词是重合的；重合越多，分数越高
def _keyword_score(query_text: str, content: str) -> float:
    query_terms = set(_tokenize(query_text))
    content_terms = set(_tokenize(content))
    if not query_terms or not content_terms:
        return 0.0
    return len(query_terms & content_terms) / math.sqrt(len(query_terms) * len(content_terms))


def _tokenize(text: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    words = [word for word in cleaned.split() if word]
    dense = "".join(words)
    tokens = words + [dense[i : i + 2] for i in range(max(1, len(dense) - 1))] if dense else []
    return tokens or [text[i : i + 2] for i in range(max(1, len(text) - 1))]


def _clip_log_text(text: str, limit: int = 80) -> str:
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."
