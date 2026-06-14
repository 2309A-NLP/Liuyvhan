import json
import re

from openai import OpenAI

from app.core.config import settings

# 工单05: Query理解优化 — 意图分类标签
QUERY_INTENT_LABELS = [
    "financial_data",       # 收入、占比、比重、增长率、发行股数等财务数值
    "org_structure",        # 组织结构、部门、销售处、上下级关系
    "tech_standard",        # 技术标准、专利、奖项、工程
    "company_info",         # 注册资本、法定代表人、基本情况
    "project_info",         # 募集资金用途、投资项目、补充流动资金
    "related_parties",      # 关联方、控制关系、持股比例
    "supply_chain",         # 上游、下游、行业企业
    "general",              # 其他通用问题
]


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

    def classify_query(self, question: str) -> dict:
        """意图分类：判断查询属于哪个类别，提取关键实体"""
        prompt = (
            f"你是一个RAG查询理解助手，负责分析用户问题。\n\n"
            f"问题：{question}\n\n"
            f"请判断这个问题属于以下哪个类别（选最匹配的一个）：\n"
            f"- financial_data: 财务数值类（收入、占比、比重、增长率、发行股数、发行后总股本等）\n"
            f"- org_structure: 组织结构类（部门、销售处、大客户销售部、组织架构、上下级关系等）\n"
            f"- tech_standard: 技术标准类（技术规范、标准、专利、国家科技进步奖、工程等）\n"
            f"- company_info: 公司基本信息类（注册资本、法定代表人、基本情况等）\n"
            f"- project_info: 项目投资类（募集资金用途、投资项目、补充流动资金等）\n"
            f"- related_parties: 关联关系类（关联方、控制关系、持股比例、控股股东等）\n"
            f"- supply_chain: 供应链类（上游、下游、行业企业等）\n"
            f"- general: 其他\n\n"
            f"请按JSON格式输出，包含以下字段：\n"
            f'{{"query_type": "类别标签", "key_entities": ["实体1", "实体2"], "confidence": 0-1}}'
        )
        try:
            response_text = self._chat([
                {"role": "system", "content": "你是一个分类器。只输出JSON，不要输出其他内容。"},
                {"role": "user", "content": prompt},
            ])
            parsed = json.loads(response_text)
            if isinstance(parsed, dict) and "query_type" in parsed:
                return parsed
        except Exception:
            pass
        # 规则兜底
        return self._rule_fallback_classify(question)

    def rewrite_query(self, question: str, query_type: str = "general",
                      conversation_history: list[dict] | None = None) -> str:
        """查询改写：Python规则预处理 + LLM润色"""
        import re
        question = question.strip()
        if not question:
            return question

        # ========== Python 规则预处理（不依赖 LLM，处理固定句式） ==========
        if conversation_history:
            last = conversation_history[-1]
            last_q = (last.get("question") or "").strip()
            last_a = (last.get("answer") or "").strip()

            # 从上次回答中提取公司全称
            company_name = ""
            if last_a:
                m = re.search(
                    r'([\u4e00-\u9fff]+(?:股份有限|有限)公司)',
                    last_a
                )
                if m:
                    company_name = m.group(1)

            # 从上次问题中提取查询主题（去掉主语部分）
            query_topic = ""
            if last_q:
                # 去掉"XX公司"、"这个公司"等主语前缀
                topic = re.sub(
                    r'^(?:武汉[\u4e00-\u9fff]*|这个|那|该)[\u4e00-\u9fff]*(?:股份有限|有限)?(?:公司)?[的]?',
                    '',
                    last_q
                ).strip().lstrip("的").strip()
                if topic:
                    query_topic = topic

            # ---- 规则1: "这个公司" / "该公司" → 替换为公司全称 ----
            if company_name and ("这个公司" in question or "该公司" in question):
                question = question.replace("这个公司", company_name)
                question = question.replace("该公司", company_name)

            # ---- 规则2: "那XXX公司呢" → 继承上轮查询主题 ----
            # 匹配"那XXX信息技术股份有限公司呢?"或"那XXX有限公司呢?"或"那XXX呢?"
            na_ne = re.match(
                r'^那([\u4e00-\u9fff]+)(?:信息技术)?(?:股份有限)?(?:有限)?公司?[呢]?\s*[?？]?\s*$',
                question
            )
            if not na_ne:
                # 宽松匹配"那XXX呢"
                na_ne = re.match(r'^那([\u4e00-\u9fff]+)呢\s*[?？]?\s*$', question)
            if na_ne and query_topic:
                new_subject = na_ne.group(1).strip() + "公司"
                rule_rewritten = f"{new_subject}的{query_topic}"
                rule_rewritten = rule_rewritten.replace("的的", "的").rstrip("？?").strip()
                if not rule_rewritten.endswith("？"):
                    rule_rewritten += "？"
                return rule_rewritten

        # ========== LLM 润色（对非规则匹配的通用情况） ==========
        type_hints = {
            "financial_data": "这是一个关于财务数值的问题。请将问题改写成包含完整年份范围和标准财务术语的检索查询。",
            "org_structure": "这是一个关于组织架构的问题。请将问题改写成包含部门名称和层级关系的检索查询。",
            "tech_standard": "这是一个关于技术标准的问题。请将问题改写成包含标准名称、编号和关键技术的检索查询。",
            "company_info": "这是一个关于公司基本信息的问题。请将问题改写成包含公司全称和注册信息的检索查询。",
            "project_info": "这是一个关于投资项目的问题。请将问题改写成包含项目名称和金额的检索查询。",
            "related_parties": "这是一个关于关联关系的问题。请将问题改写成包含关联方名称和持股比例的检索查询。",
            "supply_chain": "这是一个关于供应链的问题。请将问题改写成包含行业分类和企业名称的检索查询。",
            "general": "请将问题改写成更完整、更明确的检索查询。",
        }
        hint = type_hints.get(query_type, type_hints["general"])

        history_context = ""
        if conversation_history:
            most_recent = conversation_history[-1]
            q = most_recent.get("question", "")
            a = most_recent.get("answer", "")
            if q:
                if a:
                    history_context = f"上轮对话:\n用户: {q}\n助手: {a}\n\n"
                else:
                    history_context = f"上轮对话:\n用户: {q}\n\n"

        prompt = (
            f"你是一个检索查询改写专家。\n\n"
            f"{history_context}"
            f"用户当前问题：{question}\n\n"
            f"{hint}\n\n"
            f"要求：\n"
            f"1. 用更规范、更完整的表达替换口语化说法\n"
            f"2. 补充必要的上下文信息（如年份、金额单位）\n"
            f"3. 如果问题包含多个子问题，合并成一个完整的检索查询\n"
            f"4. 只输出改写后的查询文本，不要输出任何其他内容"
        )
        try:
            return self._chat([
                {"role": "system", "content": "你是一个查询改写专家。只输出改写后的查询文本。"},
                {"role": "user", "content": prompt},
            ])
        except Exception:
            return question

    def decompose_query(self, question: str) -> list[str]:
        """查询分解：将多问句拆分为独立子查询"""
        prompt = (
            f"你是一个查询分解助手。\n\n"
            f"用户问题：{question}\n\n"
            f"判断这个问题是否包含多个独立的子问题。如果是，请拆分成多个独立问题。\n"
            f"注意：\n"
            f"- '分别'、'和'、'及'、'与'、'、'（顿号）常是多个子问题的分隔符\n"
            f"- 每个子问题应当能独立检索\n"
            f"- 如果只有一个问题，返回包含原始问题的单元素列表\n\n"
            f"请按JSON数组格式输出，例如：\n"
            f'["子问题1", "子问题2"]'
        )
        try:
            response_text = self._chat([
                {"role": "system", "content": "你是一个查询分解助手。只输出JSON数组。"},
                {"role": "user", "content": prompt},
            ])
            parsed = json.loads(response_text)
            if isinstance(parsed, list) and len(parsed) > 0:
                return parsed
        except Exception:
            pass
        return [question]

    def _rule_fallback_classify(self, question: str) -> dict:
        """规则兜底的意图分类"""
        q = question.lower()
        type_rules = [
            ("supply_chain", ["上游", "下游", "行业企业", "供应商", "客户"]),
            ("financial_data", ["收入", "占比", "比重", "增长率", "负增长", "发行股数", "总股本",
                                "发行后", "募集资金", "金额", "万元", "净利润", "利润"]),
            ("org_structure", ["销售部", "销售处", "大客户", "部门", "结构图", "组织",
                               "架构", "隶属", "上级", "下级"]),
            ("tech_standard", ["技术标准", "技术规范", "专利", "国家科技进步", "一等奖",
                               "工程", "标准"]),
            ("company_info", ["注册资本", "法定代表人", "公司名称", "成立时间",
                              "注册地址"]),
            ("project_info", ["投资项目", "补充流动资金", "项目名称", "计划投资",
                              "拟使用", "营运资金"]),
            ("related_parties", ["关联方", "控制关系", "持股比例", "控股股东",
                                 "本公司关系", "赵马克"]),
        ]
        for query_type, tokens in type_rules:
            if any(token in q for token in tokens):
                entities = [t for t in tokens if t in q]
                return {"query_type": query_type, "key_entities": entities, "confidence": 0.7}
        return {"query_type": "general", "key_entities": [], "confidence": 0.5}

    def _chat(self, messages: list[dict]) -> str:
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY 未配置，无法调用大模型。")

        response = self.client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
