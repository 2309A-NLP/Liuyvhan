from __future__ import annotations
"""
knowledge.py 的作用是把角色数据和知识数据加载进系统，其中知识数据会被加工后存入向量知识库 Milvus。
"""
import json
from pathlib import Path

from models.schemas import KnowledgeDocument, RoleProfile
from utils.text_splitter import TextSplitter


class KnowledgeManager:
    def __init__(self, settings, mysql_client, milvus_client, embedding_service, logger):
        self.settings = settings           # 配置 告诉它种子文件在哪、知识库集合叫什么
        self.mysql_client = mysql_client   # 用来把角色资料写进基础数据库
        self.milvus_client = milvus_client # 用来把知识向量写进 Milvus
        self.embedding_service = embedding_service  # 用来把文本变成向量
        self.logger = logger
        self.splitter = TextSplitter(chunk_size=220, chunk_overlap=40) # 文本切块器  一篇知识文档太长，不能整篇直接拿去检索

    """
    在项目启动时检查知识库和角色数据是否已经准备好
    如果没准备好，就自动加载
    """
    def initialize_demo_data(self) -> None:
        self.milvus_client.ensure_collection(self.settings.knowledge_collection)
        if self._seed_sync_required():
            self.logger.info("Knowledge seed sync required. Reloading role and knowledge demo data.")
            self._load_roles()
            self._load_knowledge(reset=True)
            self.settings.demo_seed_version_path.write_text(
                self.settings.demo_seed_version,
                encoding="utf-8",
            )
            return

        if not self.mysql_client.list_roles():
            self._load_roles()
        if self.milvus_client.count(self.settings.knowledge_collection) == 0:
            self._load_knowledge(reset=False)

    """
    强制重新加载角色和知识库
    """
    def reload_demo_data(self) -> dict[str, int | str]:
        self._load_roles()
        chunk_count = self._load_knowledge(reset=True)
        self.settings.demo_seed_version_path.write_text(
            self.settings.demo_seed_version,
            encoding="utf-8",
        )
        return {
            "status": "ok",
            "message": "Demo data reloaded.",
            "roles": len(self.mysql_client.list_roles()),
            "knowledge_chunks": chunk_count,
        }
    """
    检查知识库是否需要更新
    """
    def _seed_sync_required(self) -> bool:
        version_path = self.settings.demo_seed_version_path
        if not version_path.exists():
            return True
        current_version = version_path.read_text(encoding="utf-8").strip()
        return current_version != self.settings.demo_seed_version
    """
    第一件事 - 加载角色数据 data/seed/roles.json
    """
    def _load_roles(self) -> None:
        payload = json.loads(Path(self.settings.roles_seed_path).read_text(encoding="utf-8"))
        for item in payload:
            self.mysql_client.upsert_role(RoleProfile(**item))  # 橘色信息存入 本地数据库app.db的role 表中
        self.logger.info("Loaded %s role profiles.", len(payload))
    # 读 roles.json  把里面每个角色变成 RoleProfile  写进数据库
    # RoleProfile    是来自 models / schemas.py   这个文件里规定了数据的格式
    # 对于角色数据  它统一角色数据格式 保证数据格式正确 方便代码传递


    """
    第二件事 - 加载知识库数据
    """
    def _load_knowledge(self, reset: bool) -> int:
        documents = json.loads(Path(self.settings.knowledge_seed_path).read_text(encoding="utf-8"))
        if reset:
            self.milvus_client.reset_collection(self.settings.knowledge_collection)
            self.logger.info("Knowledge collection reset before reload. collection=%s", self.settings.knowledge_collection)

        chunked_docs = []
        for item in documents:
            document = KnowledgeDocument(**item)
            chunks = self.splitter.split(document.content)  # 把一篇长知识文档拆成几个小段
            vectors = self.embedding_service.embed_texts(chunks).tolist() # 文本转向量
            # 为什么要转向量
            # 存入Milvus  语义检索  按“语义相似度”查
            for index, (chunk, vector) in enumerate(zip(chunks, vectors), start=1):
                chunked_docs.append(
                    {
                        "doc_id": f"{document.doc_id}-chunk-{index}", # 重新编码
                        # 为切块的每一小部分 重新编码 方便检索时 精确返回
                        "title": document.title,
                        "content": chunk,
                        "source": document.source,
                        "vector": vector,
                        "role_id": document.role_id, # 角色标识信息 将角色识别信息 跟随 向量一起存入Milvus
                        # 作用 后期检索的时候 识别知识块属于那个角色， 心里角色只查心里模块
                        "doc_metadata": document.metadata,
                    }
                )
        self.milvus_client.upsert_documents(self.settings.knowledge_collection, chunked_docs)
        # 我的角色数据和知识数据是通过 role_id 对应起来的
        # 虽然知识切分后会重新生成 doc_id，但每个分块都会保留原文的 role_id
        # 所以后续系统可以根据每个知识块里的 role_id 判断它属于哪个角色

        # 而是根据当前请求里已经给定的 role_id
        # 只去该角色对应的知识库数据里检索相关信息
        self.logger.info(
            "Knowledge chunks stored collection=%s count=%s",
            self.settings.knowledge_collection,
            len(chunked_docs),
        )
        return len(chunked_docs)
