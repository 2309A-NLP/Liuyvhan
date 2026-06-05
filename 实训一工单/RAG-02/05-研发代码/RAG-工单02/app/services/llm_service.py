from openai import OpenAI

from app.core.config import settings


class LLMService:
    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

    def answer_with_context(self, question: str, contexts: list[dict]) -> str:
        # 人工智能 NLP-RAG-基于 PDF文档的问答系统 将检索证据显式注入提示词，约束模型优先按原文字段作答。
        context_text = "\n\n".join(
            [
                f"[来源: 第{item['page']}页 | 分数 {item['score']:.4f} | 检索方式 {item.get('retrieval_type', 'unknown')}]\n{item['content']}"
                for item in contexts
            ]
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个基于招股说明书内容回答问题的问答助手。"
                    "你必须只根据提供的上下文作答，不允许编造，不允许补充上下文中没有的事实。"
                    "如果上下文没有明确答案，请明确回答“未在文档中找到明确答案”。"
                    "如果用户问题是中文，请用中文回答；如果用户问题是英文，请用英文回答。"
                    "回答要简洁、准确，尽量保留原文中的数字、单位、年份和并列项。"
                    "如果问题涉及上游、下游、注册资本、法定代表人、募集资金、收入、占比、比重、技术标准、工程等奖项或字段，"
                    "优先直接提取原文中的字段值、完整原句、并列类别或表格内容作答，不要泛化概括。"
                    "不要把图示标签、零散词语或相邻无关片段拼接成答案。"
                    "当上下文中出现多个候选片段时，优先采用表达最完整、最像定义句或表格字段的一条。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"问题：{question}\n\n"
                    f"上下文：\n{context_text}\n\n"
                    "请直接给出最终答案。"
                ),
            },
        ]
        return self._chat(messages)

    def answer_directly(self, question: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个通用问答助手。请直接回答用户问题。"
                    "如果信息不确定，请明确说明不确定。"
                    "如果用户问题是中文，请用中文回答；如果用户问题是英文，请用英文回答。"
                ),
            },
            {"role": "user", "content": question},
        ]
        return self._chat(messages)

    def _chat(self, messages: list[dict]) -> str:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY 未配置，无法调用大模型。")

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
