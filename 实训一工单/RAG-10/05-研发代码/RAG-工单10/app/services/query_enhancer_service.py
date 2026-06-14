"""
工单05: Query理解优化 — 完全重写

数据流：
  用户原始问题
     │
     ▼
  ┌─ Intent Classification ──┐
  │  LLM分类 + 规则兜底      │  → query_type, key_entities, confidence
  └──────────┬──────────────┘
             │
  ┌─ Query Rewrite ──────────┐
  │  LLM改写（按类别提示词）   │  → rewritten_query
  └──────────┬──────────────┘
             │
  ┌─ Synonym Expansion ──────┐
  │  同义词典扩展 + 类别术语  │  → expanded_query
  └──────────┬──────────────┘
             │
  ┌─ Query Decomposition ────┐
  │  多问句拆分 → 分别检索    │  → sub_queries[]
  └──────────┬──────────────┘
             │
             ▼
  增强后的查询 → 送入检索管道
"""

import json
from pathlib import Path

from app.core.config import settings

# 工单05: 每个意图类别相关的额外检索术语
INTENT_EXPANSION_TERMS = {
    "financial_data": [
        "2016", "2017", "2018", "2019年1-6月", "报告期内",
        "分别为", "主营业务收入", "万元", "金额",
    ],
    "org_structure": [
        "组织层级", "部门构成", "上级部门", "下级部门",
        "销售架构", "部门名称", "部门职责",
    ],
    "tech_standard": [
        "参与制定", "国家科技进步一等奖", "技术规范",
        "专利", "技术成果", "某视频技术规范",
    ],
    "company_info": [
        "发行人基本情况", "概览", "基本情况",
        "公司简介", "发行人",
    ],
    "project_info": [
        "募集资金用途", "项目名称", "金额",
        "补充流动资金", "投资金额",
    ],
    "related_parties": [
        "关联方及关联关系", "存在控制关系", "不存在控制关系",
        "与本公司关系", "持股比例",
    ],
    "supply_chain": [
        "电子元器件制造企业", "机箱", "机柜",
        "金属壳体制造企业", "军队", "政府机关",
        "能源", "行业企业",
    ],
    "general": [],
}


class QueryEnhancerService:
    def __init__(self, llm_service=None) -> None:
        self.llm_service = llm_service
        self._synonym_dict: dict[str, list[str]] | None = None

    def enhance(self, question: str, conversation_history: list[dict] | None = None) -> dict:
        """
        完整 Query 理解流水线
        conversation_history: 多轮对话历史，用于省略句/指代还原

        返回:
            original_question: 原始问题
            rewritten_query: LLM改写后的查询
            expanded_query: 同义扩展后的查询（用于Embedding/BM25检索）
            sub_queries: 分解后的子查询列表
            query_type: 意图类别
            key_entities: 关键实体
            keywords: 提取关键词（兼容旧接口）
        """
        normalized = question.strip()
        if not normalized:
            return self._empty_result(normalized)

        # 第1层: 意图分类
        classification = self._classify_query(normalized)
        query_type = classification["query_type"]
        key_entities = classification.get("key_entities", [])

        # 第2层: 查询改写（LLM）— 传入对话历史用于省略句还原
        rewritten_query = self._rewrite_query(normalized, query_type, conversation_history)

        # 第3层: 同义扩展
        expanded_query = self._expand_synonyms(rewritten_query, query_type, key_entities)

        # 第4层: 查询分解
        sub_queries = self._decompose_query(normalized)

        # 兼容旧接口: keywords
        keywords = self._extract_keywords(expanded_query)

        return {
            "original_question": normalized,
            "rewritten_query": rewritten_query,
            "expanded_query": expanded_query,
            "sub_queries": sub_queries,
            "query_type": query_type,
            "key_entities": key_entities,
            "keywords": keywords,
        }

    def _classify_query(self, question: str) -> dict:
        """意图分类 — LLM优先，规则兜底"""
        if self.llm_service and settings.enable_query_classification:
            return self.llm_service.classify_query(question)
        return self._rule_classify(question)

    def _rewrite_query(self, question: str, query_type: str,
                       conversation_history: list[dict] | None = None) -> str:
        """查询改写 — LLM改写（传入对话历史用于省略句还原）"""
        if self.llm_service and settings.enable_query_rewrite:
            return self.llm_service.rewrite_query(question, query_type, conversation_history)
        return question

    def _expand_synonyms(self, query: str, query_type: str, key_entities: list[str]) -> str:
        """同义扩展 — 词典 + 类别术语"""
        expanded_terms: list[str] = [query]

        # 第1步: 同义词词典扩展
        if settings.enable_synonym_expansion:
            synonym_dict = self._load_synonym_dict()
            for term, variants in synonym_dict.items():
                if term in query:
                    for variant in variants:
                        if variant not in query:
                            expanded_terms.append(variant)

        # 第2步: 类别相关术语扩展
        category_terms = INTENT_EXPANSION_TERMS.get(query_type, [])
        for term in category_terms:
            if term not in query:
                expanded_terms.append(term)

        # 第3步: 关键实体补充
        for entity in key_entities:
            if entity and entity not in query:
                expanded_terms.append(entity)

        # 合并去重，保持顺序
        seen: set[str] = set()
        merged: list[str] = []
        for term in expanded_terms:
            lower_term = term.lower().strip()
            if lower_term and lower_term not in seen:
                seen.add(lower_term)
                merged.append(term.strip())

        return " ".join(merged)

    def _decompose_query(self, question: str) -> list[str]:
        """查询分解 — 多问句拆分"""
        if self.llm_service:
            try:
                return self.llm_service.decompose_query(question)
            except Exception:
                pass
        return [question]

    def _load_synonym_dict(self) -> dict[str, list[str]]:
        """加载同义词词典"""
        if self._synonym_dict is not None:
            return self._synonym_dict

        synonym_path = Path(settings.synonym_dict_path)
        if not synonym_path.exists() or not synonym_path.is_file():
            self._synonym_dict = {}
            return self._synonym_dict

        try:
            self._synonym_dict = json.loads(synonym_path.read_text(encoding="utf-8"))
        except Exception:
            self._synonym_dict = {}
        return self._synonym_dict

    def _rule_classify(self, question: str) -> dict:
        """纯规则意图分类（无LLM时兜底）"""
        q = question.lower()
        type_rules = [
            ("supply_chain", ["上游", "下游", "行业企业", "供应商", "客户"]),
            ("financial_data", [
                "收入", "占比", "比重", "增长率", "负增长", "发行股数", "总股本",
                "发行后", "募集资金", "金额", "万元", "净利润", "利润",
            ]),
            ("org_structure", [
                "销售部", "销售处", "大客户", "部门", "结构图", "组织",
                "架构", "隶属", "上级", "下级",
            ]),
            ("tech_standard", [
                "技术标准", "技术规范", "专利", "国家科技进步", "一等奖", "工程", "标准",
            ]),
            ("company_info", ["注册资本", "法定代表人", "公司名称", "成立时间", "注册地址"]),
            ("project_info", [
                "投资项目", "补充流动资金", "项目名称", "计划投资", "拟使用", "营运资金",
            ]),
            ("related_parties", [
                "关联方", "控制关系", "持股比例", "控股股东", "本公司关系", "赵马克",
            ]),
        ]
        for query_type, tokens in type_rules:
            matched = [t for t in tokens if t in q]
            if matched:
                return {"query_type": query_type, "key_entities": matched, "confidence": 0.7}
        return {"query_type": "general", "key_entities": [], "confidence": 0.5}

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词（兼容旧接口）"""
        candidates = [
            "报告期内", "军用领域", "收入", "主营业务收入", "占比", "比重",
            "上游", "下游", "企业", "行业", "技术标准", "工程",
            "注册资本", "法定代表人", "募集资金", "补充流动资金",
            "发行股数", "发行后总股本", "关联方", "控制关系", "持股比例",
            "本公司关系", "分别", "电子信息行业", "组织结构图", "结构图",
            "图像", "图片", "图表", "增长率", "负增长", "销售部",
            "大客户销售部", "销售处",
        ]
        import re
        matched = [item for item in candidates if item in text]
        years = re.findall(r"(20\d{2}|2019年1-6月)", text)
        return list(dict.fromkeys(matched + years))

    def _empty_result(self, question: str) -> dict:
        return {
            "original_question": question,
            "rewritten_query": question,
            "expanded_query": question,
            "sub_queries": [question],
            "query_type": "general",
            "key_entities": [],
            "keywords": [],
        }
