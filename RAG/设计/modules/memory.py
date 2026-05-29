from __future__ import annotations
"""
记忆管理 调度长短期记忆
短期记忆：按 session_id 管，主要走 Redis
长期记忆：按 user_id 管，主要走 Milvus
"""
from datetime import datetime

from utils.text_sanitizer import looks_corrupted_text, normalize_text
# normalize_text --- 文本清洗函数         looks_corrupted_text --- 检查这条消息内容看起来是不是乱码或者脏文本
# 去掉奇怪空白
# 统一换行
# 修正某些异常字符
# 做基础规范化

class MemoryManager:
    """记忆层编排器：短期记忆走 Redis，长期记忆走 Milvus。"""
    """
    初始化记忆管理器 -- 把外面传进来的工具保存到自己身上
    """
    def __init__(self, settings, redis_client, milvus_client, embedding_service, logger):
        self.settings = settings
        self.redis_client = redis_client
        self.milvus_client = milvus_client
        self.embedding_service = embedding_service
        self.logger = logger
        self.storage_mode = f"{milvus_client.storage_mode}/{redis_client.storage_mode}" #  self--当前这个 MemoryManager 对象自己 storage_mode - 属性/变量 给当前 MemoryManager 对象新增/设置一个属性，名字叫 storage_mode
        # milvus_client.storage_mode --- 长期记忆这层现在实际使用的存储模式
        # redis_client.storage_mode --- 短期记忆这层现在实际使用的存储模式
        # 拼起来为什么有意义 ???
        # 情况 1                         情况 2                        情况 3
        # 长期记忆正常，短期记忆正常：       长期记忆降级成文件，短期记忆正常：  长期记忆正常，短期记忆降级成文件：
        # "milvus/redis"                "file/redis"                  "milvus/file"
        # 给当前 MemoryManager 对象贴一个标签，写明“长期记忆/短期记忆分别用什么后端”

        self.milvus_client.ensure_collection(settings.long_memory_collection)
        # 作用 --- 确保长期记忆的 Milvus 集合存在
        # ensure --- 看这个 collection 在 Milvus 里有没有 如果有，就直接用  如果没有，就创建出来
        # settings.long_memory_collection ---  这是配置里定义的长期记忆集合名 Milvus 里专门存长期记忆的那张“向量表”的名字
        # 确保 Milvus 中用于长期记忆存储的集合已经准备完毕，后续可直接写入和检索。


    """
    按会话 ID 读取短期记忆
    """
    def get_short_memory(self, session_id: str) -> list[dict]:
        # 短期记忆按 session 读取。
        # 读出来后会顺手做一次清洗，避免把乱码和脏文本继续送进模型。
        messages = self.redis_client.get_messages(session_id)
        # 通过会话 ID 在redis 读取短期记忆
        # 取出结果：列表
        # [
        #     {"role": "user", "content": "我最近很焦虑", "timestamp": "..."},
        #     {"role": "assistant", "content": "你愿意具体说说吗？", "timestamp": "..."}
        # ]

        cleaned_messages: list[dict] = []
        #  创建新的空列表 中字典格式
        #  原始 messages 可能有问题 标准化的时候肯会丢失信息 创建新的类别存放清洗后信息

        mutated = False
        # 准备一个“是否发生变化”的标记 - 这是一个布尔变量
        # 你可以把它理解成一个是否修改过数据的开关。
        # False：没改过，不用回写
        # True：改过了，要把干净版本重新存回 Redis

        for item in messages:
            content = normalize_text(item.get("content", ""))  # 文本清洗函数
            # item = {
            #     "role": "user",
            #     "content": " 原始内容 ",
            #     "timestamp": "2026-05-10T10:00:00"
            # 从字典 item 里取 "content" 这个字段   如果没有这个字段，就给一个默认空字符串 ""
            # 为什么用 .get() 而不是 item["content"]？ --- 有这个字段就取出来  没有也不会立刻报错


            if looks_corrupted_text(content, expect_chinese=True): # 检查这条消息内容看起来是不是乱码或者脏文本
                mutated = True
                continue
            # 如果这条数据是脏文本 进入 mutated = True--消息列表发生过清洗变化了
            # continue --- 因为这条消息将不会保留
            # 跳过当前这条消息，不把它加入 cleaned_messages，直接进入下一轮循环  并标记“数据发生了变化

            normalized_item = {**item, "content": content}  # 新的消息字典---先保留原来 item 里的所有字段 再把 "content" 字段替换成清洗后的 content
            # **item
            # item = {
            #     "role": "user",
            #     "content": " 原始内容 ",
            #     "timestamp": "2026-05-10T10:00:00"
            # }
            if normalized_item != item:
                mutated = True
            cleaned_messages.append(normalized_item)
            # mutated = True 为什么要做这个判断
            # 因为有些消息虽然不是乱码，但 normalize_text() 可能还是改了一些细节，比如：去掉多余空格 统一换行 修正奇怪字符
            # 如果改过，就说明 Redis 里的原始内容不是最佳版本，后面应该回写干净版。

        if mutated:
            self.redis_client.set_messages(session_id, cleaned_messages)
            # 如果前面清洗过程中发生过任何变化，就把清洗后的结果重新存回 Redis。
            # 把 Redis 里的旧脏数据更新成最新干净版本
        return cleaned_messages

    def append_turn(self, session_id: str, user_message: str, assistant_message: str) -> None:
        max_items = max(1, self.settings.short_memory_turns * 2)
        timestamp = datetime.utcnow().isoformat()

        user_content = normalize_text(user_message)
        assistant_content = normalize_text(assistant_message)

        if not looks_corrupted_text(user_content, expect_chinese=True):
            self.redis_client.push_message(
                session_id,
                {
                    "role": "user",
                    "content": user_content,
                    "timestamp": timestamp,
                },
                max_items=max_items,
            )

        if not looks_corrupted_text(assistant_content, expect_chinese=True):
            self.redis_client.push_message(
                session_id,
                {
                    "role": "assistant",
                    "content": assistant_content,
                    "timestamp": timestamp,
                },
                max_items=max_items,
            )

    """
    用来判断“这条用户消息值不值得进入长期记忆”，如果值得，就转向量并写入 Milvu
    """
    def maybe_write_long_term(self, user_id: str, role_id: str, session_id: str, message: str) -> None:
        # 长期记忆不是每句话都存。
        # 当前规则只抓“身份、偏好、目标、意愿”这类更适合长期保留的信息。
        message = normalize_text(message) # normalize_text清洗函数---先把用户消息整理成更干净的标准文
        if looks_corrupted_text(message, expect_chinese=True): # 检查这条消息是不是疑似乱码或脏文本  如果是直接放弃
            return    # 直接结束函数，不写长期记忆
        if not any(keyword in message for keyword in ("我喜欢", "我是", "我的目标", "我希望", "我不想")):# 判断是否符合存入长期规则 这些关键词都是用户核心信息
            # any(...) 的意思 --- 只要里面有一个条件为真，就返回 True
            # 只要命中一个，就说明这句话可能包含长期有价值的信息
            # not any 判断一个关键词都不包含 直接退出不存
            # 总结 --- 只有当用户消息看起来像“身份/偏好/目标/意愿表达”时，才允许进入长期记忆
            return

        doc_id = f"memory-{user_id}-{session_id}-{abs(hash(message))}" # 为这条长期记忆生成一个唯一文档编号，方便后续存储和检索。
        # doc_id --- memory-user_001-session_123-987654321
        # memory --- 表示这是长期记忆类文档
        # abs(hash(message))
        # hash(message) ---  hash() 是 Python 内置函数 作用--根据一个对象的内容，计算出一个整数哈希值 -> -48392017428123  更加可以区分内容
        # abs() 是 Python 内置函数 哈希算法可能是负数

        # 长期记忆也要先向量化，后面才能按语义相似度检索。
        vector = self.embedding_service.embed_text(message).tolist() # 文本转向量
        # .tolist() 作用
            # self.embedding_service.embed_text(message) 转向量返回类型 NumPy 数组-> array([0.12, -0.08, 0.33])
            # tolist()将数组转成 Python 列表 -> [0.12, -0.08, 0.33]
            #  Milvus 文档结构

        # 把长期记忆写进 Milvus
        self.milvus_client.upsert_documents(
            # update + insert --- 如果文档已存在，就更新；如果不存在，就插入
            self.settings.long_memory_collection,  # 这个 collection 是专门用来存长期记忆的
            [
                {
                    "doc_id": doc_id,        # 长期记忆文档的唯一编号
                    "title": "用户长期偏好",    # 简要标签 标注文档大概类型 可读性
                    "content": message,       # 真正要保存的文本内容
                    "source": "chat_memory",  # 标注数据来源->这条文档来自聊天记忆抽取，不是知识库种子文件
                    "vector": vector,         # 这条文本对应的向量  `Milvus 是向量库，后续语义搜索主要靠这个字段
                    "role_id": role_id,
                    "user_id": user_id,       #用户id -- 表示这条长期记忆属于哪个用户 -
                    # 字段重要 后续检索长期记忆会按照 用户字段
                }
            ],
        )
        # 把这次写入动作记到日志里
        self.logger.info(
            "Long-memory stored doc_id=%s user_id=%s role_id=%s session_id=%s",
            # 日志模板  --- 后面的参数会依次填进去
            doc_id,
            user_id,
            role_id,
            session_id,
        )

    """
    用来按用户 ID，在长期记忆库里搜索和当前问题相关的长期记忆 - 
    所以这个函数不是查“所有长期记忆”， 而是查：“某个用户自己的长期记忆里，和当前问题相关的部分。
    search_long_memory - 作用
    把当前查询文本转成向量
    去 Milvus 搜长期记忆
    按 user_id 过滤，只查当前用户
    清洗结果文本
    记录日志并返回结果
    """
    def search_long_memory(self, user_id: str, query: str) -> list[dict]:
        # user_id --- 这里的查询长期记忆按照 user_id  query---当前查询文本，一般就是用户这轮输入的话
        # list[dict] --- 返回值是一个列表，列表里每一项是一个字典 每个字典通常表示一条命中的长期记忆

        query_vector = self.embedding_service.embed_text(query) # 问题转向量

        results = self.milvus_client.search(
            collection_name=self.settings.long_memory_collection,  # 去哪个 collection 里查去专门存长期记忆的那张 Milvus “向量表”里查
            query_vector=query_vector,
            query_text=query,
            # 为什么传入原始文本---因为你的 milvus_client.search(...) 不一定是纯向量检索，
            # 有可能内部还做了：关键词匹配   混合打分    日志记录  调试用途
            top_k=self.settings.long_memory_top_k, # 最多返回多少条命中结果  top_k取最相关的前 K 条
            filters={"user_id": user_id},          # 只在 user_id 等于当前用户的长期记忆里查
            # 这正是长期记忆和知识库的重要区别：
            # 知识库可以是角色级共享资料
            # 长期记忆必须是用户私有信息
            # 所以这里一定要按 user_id 过滤，避免查到别人的长期记忆
        )
        cleaned_results: list[dict] = []
        for item in results:
            content = normalize_text(item.get("content", "")) # 清洗规范检索出的长期记忆
            if looks_corrupted_text(content, expect_chinese=True): # 检查消息是否是乱码或者脏文本
                continue
            cleaned_results.append({**item, "content": content})
        self.logger.info(
            "Long-memory search user_id=%s hits=%s query=%s",
            user_id,
            len(cleaned_results),
            " ".join(str(query).split())[:80],
        )
        return cleaned_results
"""
search_long_memory() 的作用是：
先把当前查询文本转成向量，再到 Milvus 的长期记忆集合中按 user_id 过滤检索最相关的几条长期记忆；
随后对结果做文本清洗和乱码过滤，记录查询日志，最后返回干净的长期记忆结果列表。
"""
