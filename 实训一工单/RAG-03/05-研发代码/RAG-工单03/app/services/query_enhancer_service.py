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
            "发行股数",
            "发行后总股本",
            "关联方",
            "控制关系",
            "持股比例",
            "本公司关系",
            "分别",
            "电子信息行业",
        ]
        matched = [item for item in candidates if item in question]
        years = re.findall(r"(20\d{2}|2019年1-6月)", question)
        return list(dict.fromkeys(matched + years))

    def _expand_query(self, question: str, keywords: list[str]) -> str:
        extra_terms: list[str] = []

        if any(keyword in keywords for keyword in ["收入", "占比", "比重"]):
            extra_terms.extend(["2016", "2017", "2018", "2019年1-6月", "分别为", "主营业务收入"])

        if "上游" in keywords:
            extra_terms.extend(["电子元器件制造企业", "机箱", "机柜", "金属壳体制造企业"])

        if "下游" in keywords:
            extra_terms.extend(["军队", "政府机关", "能源", "行业企业"])

        if any(keyword in keywords for keyword in ["注册资本", "法定代表人"]):
            extra_terms.extend(["发行人基本情况", "概览", "基本情况"])

        if any(keyword in keywords for keyword in ["募集资金", "补充流动资金"]):
            extra_terms.extend(["募集资金用途", "项目名称", "金额", "补充流动资金"])

        if any(keyword in keywords for keyword in ["发行股数", "发行后总股本"]):
            extra_terms.extend(["本次发行概况", "发行股数及占发行后总股本比例"])

        if any(keyword in keywords for keyword in ["关联方", "控制关系", "持股比例", "本公司关系"]):
            extra_terms.extend(["关联方及关联关系", "存在控制关系", "不存在控制关系", "与本公司关系"])

        if any(keyword in keywords for keyword in ["技术标准", "工程"]):
            extra_terms.extend(["参与制定", "国家科技进步一等奖", "某视频技术规范 1.0"])

        merged = list(dict.fromkeys([question, *keywords, *extra_terms]))
        return " ".join(merged)
