from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from models.schemas import ChatRequest, ChatResponse
# ChatRequest --- 规定前端传入后端 信息的格式
# ChatResponse --- 规定后端调用完大模型后 信息 传入前端的格式
from modules.role_prompts import build_system_prompt


@dataclass
class ChatContext:
    # 这是一次对话真正送进大模型前的完整上下文。
    """
    建立一个 装信息的盒子
    """
    role: object              # 当前角色信息
    short_memory: list[dict]  # 当前会话的短期记忆
    long_memory: list[dict]   # 长期记忆中的相关内容
    references: list          # 从知识库检索出来的参考资料
    system_prompt: str        # 最终拼好的系统提示词


class ChatService:
    """对话总编排器：把角色、记忆、检索和大模型调用串成一条链。"""
    """
    配置工具
    """
    def __init__(self, settings, mysql_client, retriever, memory_manager, llm_client, logger):
        self.settings = settings
        self.mysql_client = mysql_client     # 查角色信息
        self.retriever = retriever           # 查知识库
        self.memory_manager = memory_manager # 管理短期记忆和长期记忆
        self.llm_client = llm_client
        self.logger = logger

    """
    一次返回结果 接口对调试、测试、脚本调用、第三方集成和保留标准接口都很有价值
    """
    def chat(self, payload: ChatRequest) -> ChatResponse:
        # 先组上下文，再调用模型，最后把结果写回记忆层。
        # 先把这一轮聊天需要的上下文材料准备好
        # 当前角色
        # 短期记忆
        # 长期记忆
        # 检索出来的知识
        # system prompt
        context = self._build_context(payload)

        # ·调用大模型  把刚才准备好的材料交给大模型
        # 生成最终答案
        answer = self.llm_client.generate(
            role=context.role,               # 当前角色信息 告诉模型下载那个身份在回答
            message=payload.message,         # 用户这次真正发来的问题
            short_memory=context.short_memory,  # 最近几轮对话内容
            long_memory=context.long_memory, # 这个用户以前有哪些长期信息和当前问题相关。
            references=context.references,   # 从知识库检索出来的参考资料 回答这个问题时，可以参考这些知识片段
            system_prompt=context.system_prompt,
        )
        return self._finalize_response(payload, context.references, answer)
        # payload --- 是一个变量名 装着前端发给后端的一整包请求内容
        # 这包数据格式：payload: ChatRequest
        # user_id      # 这是哪个用户 是谁再发起聊天          作用：查这个用户的长期记忆 做用户级的数据归属
        # session_id   # 当前是哪一个会话  这是哪一个聊天窗口  作用：查短期记忆把这轮聊天继续接到同一段上下文里
        # role_id      # 这次聊天选的是哪个角色              作用：查角色设定 限制检索哪个角色的知识库 决定回答风格
        # message      # 问题内容

        # context.references --- context.references  当前端询问答案生成参考那些资料 返回这个
    """
    流式聊天
    """
    def stream_chat(self, payload: ChatRequest) -> Iterator[dict]:
        # payload --- 是一个变量名 装着前端发给后端的一整包请求内容
        # 这包数据格式：
        # user_id
        # session_id
        # role_id
        # message

        # ChatRequest --- 定义在models/schemas.py 是一种数据模式 专门规定聊天请求数据格式

        context = self._build_context(payload) # 先把这一轮聊天需要的背景材料准备好。

        def event_stream() -> Iterator[dict]:  # 这个函数会不断往外吐一条一条的数据。
            # 流式模式下，先不断吐 chunk 给前端，最后再统一落库。
            answer_parts: list[str] = []
            try:
                for chunk in self.llm_client.generate_stream(
                    role=context.role,
                    message=payload.message,
                    short_memory=context.short_memory,
                    long_memory=context.long_memory,
                    references=context.references,
                    system_prompt=context.system_prompt,
                ):
            # payload.message，而不是像字典一样写 payload["message"]
            # FastAPI 收到前端传来的 JSON 数据会按照 ChatRequest 这个模型去解析    最后得到的不是原始字典，而是一个 ChatRequest 对象 这是一种对象属性访问
                    if not chunk:
                        continue
                    answer_parts.append(chunk)
                    yield {"type": "chunk", "content": chunk}

                answer = "".join(answer_parts).strip()
                response = self._finalize_response(payload, context.references, answer)
                yield {
                    "type": "done",
                    "answer": response.answer,
                    "references": [self._serialize_reference(item) for item in response.references],
                    "memory_size": response.memory_size,
                    "session_id": response.session_id,
                    "role_id": response.role_id,
                }
            except Exception as exc:
                self.logger.exception("Streaming chat failed for session=%s", payload.session_id)
                yield {"type": "error", "detail": str(exc)}

        return event_stream()

    def _build_context(self, payload: ChatRequest) -> ChatContext:
        # 第一步：查角色。角色决定系统提示词的语气、规则和知识域。
        role = self.mysql_client.get_role(payload.role_id)
        # payload.role_id 根据角色id 在mysql 中查找角色
        if role is None:  # 角色不存在 报错
            raise KeyError(f"Role {payload.role_id} not found.")
            # 这里抛出 KeyError，最后会被 main.py 的路由函数接住，转成 404。

         # 第二步：读取当前 session 的短期记忆。取回这个会话最近聊过的内容，作为上下文。
        short_memory = self.memory_manager.get_short_memory(payload.session_id)

        #      # 第三步：并行做两件事，减少单轮等待时间：
        #             # 1. 查用户长期记忆
        #             # 2. 查角色知识库
        with ThreadPoolExecutor(max_workers=2) as executor: # 创建线程池对象 名称executor 在 with 代码块里使用它 代码块结束后自动清理线程资源

            # ThreadPoolExecutor --- 线程池执行器 一个可以同时安排几个后台工人干活的工具
            # max_workers = 2 --- 开两个工作线程  一个线程查长期记忆  一条现成查知识库

            long_memory_future = executor.submit(
                self.memory_manager.search_long_memory,
                payload.user_id, # 去“这个用户”的长期记忆里，搜索和“这句话”相关的内容
                payload.message,
            )
            # submit --- 把一个任务提交给线程池去后台执行
            # executor.submit(要执行的函数, 参数1, 参数2, ...) --- 把函数任务 + 参数 交给线程池 线程池安排某个线程运行
            # 然后先返回一个“结果占位符    long_memory_future --- 长期记忆查询任务已经发出去了，结果以后再取。”
            # long_memory_future 为什么是取号 没有结果 查询任务已经交给线性池 不等结果 先去把别的任务发送
            references_future = executor.submit(
                self.retriever.retrieve,
                payload.message,
                payload.role_id,
            )
            long_memory = long_memory_future.result()
            references = references_future.result()
            # long_memory_future 这一步是取号
            # result() 这就是在取结果了

        # 第四步：把角色设定、用户当前问题、短期记忆、长期记忆、检索知识
        # 全部组装成 system prompt，最终喂给大模型。
        system_prompt = build_system_prompt(
            role=role,
            user_message=payload.message, # 用户问题
            short_memory=short_memory, # 短期记忆
            long_memory=long_memory,   # 长期记忆
            references=references,   # 知识库信息
        )
        # build_system_prompt 这个函数是封装给大模型的提示词from modules.role_prompts import build_system_prompt
        return ChatContext(
            role=role,
            short_memory=short_memory,
            long_memory=long_memory,
            references=references,
            system_prompt=system_prompt,
        )
    """
    保存对话记录 长期记忆 短期记忆 
    """
    def _finalize_response(self, payload: ChatRequest, references: list, answer: str) -> ChatResponse:
        # payload: ChatRequest --- 请求聊天的原始数据
        # references --- 这轮回答用到的知识库参考资料
        # 先写短期记忆，再尝试抽取长期记忆。
        # 这样下一轮请求就能读到刚刚发生过的对话。
        """

        """
        """
        存入短期记忆 --- 作用：保证会话上下文连续 防止断连
        短期记忆 按会话归属
        """
        self.memory_manager.append_turn(payload.session_id, payload.message, answer)
        # append_turn --- 这个函数意思是不止存入一条 将一轮完整对话存入
        # payload.session_id --- 会话id 短期记忆是按会话存到 所以必须知道往哪个会话里写
        # payload.message --- 用户问题/这轮说的话


        """
        存入长期记忆
        长期记忆 按用户归属
        """
        self.memory_manager.maybe_write_long_term(
            user_id=payload.user_id,         # 确定长期记忆的用户 - 这条长期记忆属于哪个用户
            role_id=payload.role_id,         # 确定对话的角色信息
            session_id=payload.session_id,   # 这条记忆是在哪个会话里出现的 方便追踪来源
            message=payload.message,
            # 注意：
            # 当前代码传进去的是用户消息 说明长期记忆抽取主要针对：
            # 用户自己说出来的信息 因为长期记忆重点是记住用户
        )
        # maybe_write_long_term --- 内部流程
        #  检查这条消息是否值得长期保存
        # 如果值得，就向量化
        # 写入 Milvus 长期记忆集合
        # 记录日志

        """
        构造返回对象 --- 把本轮最终要返回给前端的数据打包成 ChatResponse
        
        """
        return ChatResponse(
            session_id=payload.session_id,# 作用--- 前端还需要知道这条回复属于哪个会话
            # 页面可能有多个对话用户可能切换不同会话 前端要知道这次返回的数据该挂到哪个聊天窗口
            role_id=payload.role_id,      # 当前角色
            # 页面上可能显示当前角色标签 前端要确认这是哪个角色的回答  多角色切换时要保证结果不
            answer=answer,
            references=references,         # 前端可能需要参考资料
            # 页面可以展示“本次回答参考了哪些知识” 方便做可解释性展示 后面如果要加“来源卡片”或“知识引用区”，就直接能用
            memory_size=len(self.memory_manager.get_short_memory(payload.session_id)), # 当前记忆窗口大小
            # 可以知道当前会话上下文大小 调试时很有用 后续做前端状态展示或排错也有价值
        )

    @staticmethod
    def _serialize_reference(reference) -> dict:
        if hasattr(reference, "model_dump"):
            return reference.model_dump()
        return reference.dict()
