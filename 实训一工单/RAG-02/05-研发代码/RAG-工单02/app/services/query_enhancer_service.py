import re


class QueryEnhancerService:
    def enhance(self, question: str) -> dict:
        normalized = question.strip()
        keywords = self._extract_keywords(normalized)
        expanded_query = self._expand_query(normalized, keywords)
        return {
            "original_question": normalized,
            "expanded_query": expanded_query,
            "keywords": keywords,
        }

    def _extract_keywords(self, question: str) -> list[str]:
        candidates = [
            "报告期内",
            "军用领域",
            "收入",
            "主营业务收入",
            "占比",
            "比重",
            "上游",
            "下游",
            "企业",
            "行业",
            "技术标准",
            "工程",
            "注册资本",
            "法定代表人",
            "募集资金",
            "补充流动资金",
            "分别",
            "电子信息行业",
        ]
        matched = [item for item in candidates if item in question]
        years = re.findall(r"(20\d{2}|2019年?1-6月)", question)
        return list(dict.fromkeys(matched + years))

    def _expand_query(self, question: str, keywords: list[str]) -> str:
        extra_terms: list[str] = []

        if "收入" in keywords or "占比" in keywords or "比重" in keywords:
            extra_terms.extend(["2016", "2017", "2018", "2019年1-6月", "分别为", "主营业务收入"])

        if "上游" in keywords:
            extra_terms.extend(["电子元器件制造企业", "金属壳体制造企业", "机箱", "机柜"])

        if "下游" in keywords:
            extra_terms.extend(["军队", "政府机关", "能源", "行业企业"])

        if "注册资本" in keywords:
            extra_terms.extend(["基本情况", "公司概况"])

        if "法定代表人" in keywords:
            extra_terms.extend(["基本情况", "公司概况"])

        if "募集资金" in keywords or "补充流动资金" in keywords:
            extra_terms.extend(["投资项目", "募集资金用途", "金额"])

        if "技术标准" in keywords or "工程" in keywords:
            extra_terms.extend(["参与制定", "荣获", "国家科技进步一等奖"])

        merged = list(dict.fromkeys([question, *keywords, *extra_terms]))
        return " ".join(merged)
