"""
智能体逻辑模块 - 对话管理与业务逻辑编排
工单编号：人工智能NLP-Agent数字人项目-01-记账本任务工单V1.1-20250206
"""

import re
from datetime import date, datetime
from typing import Optional

from config import FAMILY_MEMBERS
from agent_parser import parse_input
import database as db


class AgentState:
    """对话状态"""
    IDLE = "idle"
    PENDING_CONFIRM_ADD = "pending_confirm_add"
    PENDING_CONFIRM_DELETE = "pending_confirm_delete"
    PENDING_CONFIRM_UPDATE = "pending_confirm_update"
    PENDING_INFO = "pending_info"


class AccountBookAgent:
    """记账本智能体"""

    def __init__(self):
        self.state = AgentState.IDLE
        self.pending_data = None  # 待确认的数据
        self.conversation_started = False

    def reset(self):
        """重置状态"""
        self.state = AgentState.IDLE
        self.pending_data = None

    def get_pending_info_message(self, parsed: dict) -> str:
        """生成引导补充信息的消息"""
        missing = parsed["missing"]
        member_missing = "成员" in missing
        amount_missing = "金额" in missing

        msg = "信息还不太完整，"
        if member_missing and amount_missing:
            msg += "请问是谁？花了多少钱（或收了多少钱）？"
        elif member_missing:
            msg += "请问是谁（爸爸、妈妈还是女儿）？"
        elif amount_missing:
            msg += "请问花了（或收了）多少钱？"

        # 附带已解析的部分信息
        data = parsed["data"]
        parts = []
        if data["record_date"]:
            parts.append(f"{data['record_date'].year}年{data['record_date'].month}月{data['record_date'].day}日")
        if data["category"]:
            parts.append(data["category"])
        if data["type"]:
            parts.append(data["type"])

        if parts:
            date_str = data["record_date"].strftime("%Y年%m月%d日") if data["record_date"] else ""
            items = []
            if date_str:
                items.append(date_str)
            if data["member"]:
                items.append(data["member"])
            items.append(data["category"])
            msg = f"已识别：{''.join(items)}。{msg}"

        return msg

    def process_message(self, user_input: str) -> dict:
        """
        处理用户消息，返回响应
        返回: {
            "type": "text" | "query_result" | "confirm_add" | "confirm_delete" | "confirm_update" | "greeting",
            "content": str,  # 文本内容
            "data": any,     # 附加数据
        }
        """
        text = user_input.strip()

        # 检测是否是首条消息（开场白）
        if not self.conversation_started:
            self.conversation_started = True
            # 如果用户直接输入内容，先做解析
            return self._handle_input(text)

        return self._handle_input(text)

    def _handle_input(self, text: str) -> dict:
        """处理各类输入"""
        # 如果在等待确认或补充信息状态
        if self.state in (AgentState.PENDING_CONFIRM_ADD,
                          AgentState.PENDING_CONFIRM_DELETE,
                          AgentState.PENDING_CONFIRM_UPDATE,
                          AgentState.PENDING_INFO):
            return self._handle_confirmation(text)

        # 检测查询意图
        query_result = self._detect_query(text)
        if query_result:
            return query_result

        # 检测删除意图
        delete_result = self._detect_delete(text)
        if delete_result:
            return delete_result

        # 检测修改意图
        update_result = self._detect_update(text)
        if update_result:
            return update_result

        # 默认：记账意图解析
        return self._handle_add(text)

    def _handle_add(self, text: str) -> dict:
        """处理记账添加"""
        parsed = parse_input(text)

        if not parsed["success"]:
            # 信息不完整，进入待补充信息状态
            self.state = AgentState.PENDING_INFO
            self.pending_data = parsed["data"]
            msg = self.get_pending_info_message(parsed)
            return {"type": "text", "content": msg}

        # 信息完整，进入确认状态
        data = parsed["data"]
        self.state = AgentState.PENDING_CONFIRM_ADD
        self.pending_data = data

        # 将 date 对象转为字符串，避免 JSON 序列化失败
        data_json = self._prepare_data_for_json(data)

        date_str = data["record_date"].strftime("%Y年%m月%d日")
        amount_str = f"+{data['amount']}元" if data["type"] == "收入" else f"{data['amount']}元"

        confirm_msg = (f"即将记录：{date_str}，{data['member']}，"
                       f"{data['type']}，{data['category']}，"
                       f"{data['item']}，{amount_str}。确认吗？")
        return {"type": "confirm_add", "content": confirm_msg, "data": data_json}

    def _prepare_data_for_json(self, data: dict) -> dict:
        """将 data 中的 date 对象转为字符串，确保可 JSON 序列化"""
        json_data = {}
        for k, v in data.items():
            if isinstance(v, date):
                json_data[k] = v.strftime("%Y-%m-%d")
            elif v is not None:
                json_data[k] = v
            else:
                json_data[k] = v
        return json_data

    def _merge_with_pending(self, new_text: str) -> str:
        """将用户补充的信息与之前的待补充数据合并，生成完整的描述文本"""
        pending = self.pending_data or {}
        merged = new_text
        if pending.get("record_date"):
            ds = pending["record_date"].strftime("%Y年%m月%d日") if hasattr(pending["record_date"], 'strftime') else str(pending["record_date"])
            if ds not in merged:
                merged = ds + merged
        if pending.get("member") and pending["member"] not in merged:
            merged = pending["member"] + merged
        if pending.get("category") and pending["category"] not in merged:
            merged = merged + pending["category"]
        return merged

    def _handle_confirmation(self, text: str) -> dict:
        """处理确认/取消响应"""
        confirm = any(kw in text for kw in ["确认", "是的", "对", "好", "可以", "嗯", "确认无误"])
        cancel = any(kw in text for kw in ["取消", "不对", "不是", "删除", "不", "不要", "错了", "改"])

        # 补充信息状态：用户正在补充缺失的字段
        if self.state == AgentState.PENDING_INFO:
            # 将新的输入与已有pending_data合并解析
            full_text = self._merge_with_pending(text)
            parserd = parse_input(full_text)
            if parserd["success"]:
                # 信息完整，进入确认
                data = parserd["data"]
                self.state = AgentState.PENDING_CONFIRM_ADD
                self.pending_data = data
                data_json = self._prepare_data_for_json(data)
                date_str = data["record_date"].strftime("%Y年%m月%d日")
                amount_str = f"+{data['amount']}元" if data["type"] == "收入" else f"{data['amount']}元"
                confirm_msg = (f"即将记录：{date_str}，{data['member']}，"
                               f"{data['type']}，{data['category']}，"
                               f"{data['item']}，{amount_str}。确认吗？")
                return {"type": "confirm_add", "content": confirm_msg, "data": data_json}
            else:
                # 仍然缺少信息
                msg = self.get_pending_info_message(parserd)
                return {"type": "text", "content": msg}

        if self.state == AgentState.PENDING_CONFIRM_ADD:
            if confirm:
                data = self.pending_data
                result = db.add_record(
                    data["record_date"], data["member"], data["type"],
                    data["category"], data["item"], data["amount"]
                )
                self.reset()
                if result["success"]:
                    return {"type": "text", "content": "已记录成功！还有什么需要帮忙的吗？"}
                return {"type": "text", "content": "记录失败，请稍后再试。"}
            elif cancel:
                self.reset()
                return {"type": "text", "content": "已取消记录。请重新输入。"}
            else:
                return {"type": "text", "content": "请回复确认或取消。"}

        elif self.state == AgentState.PENDING_CONFIRM_DELETE:
            if confirm:
                ids = [r["id"] for r in self.pending_data]
                count = db.delete_records(ids)
                self.reset()
                return {"type": "text", "content": f"已成功删除 {count} 条记录。"}
            elif cancel:
                self.reset()
                return {"type": "text", "content": "已取消删除操作。"}
            else:
                return {"type": "text", "content": "请回复确认来删除，或回复取消。"}

        elif self.state == AgentState.PENDING_CONFIRM_UPDATE:
            if confirm:
                data = self.pending_data
                # data contains: id, record_date, member, type, category, item, amount
                success = db.update_record(
                    data["id"], data["record_date"], data["member"],
                    data["type"], data["category"], data["item"], data["amount"]
                )
                self.reset()
                if success:
                    return {"type": "text", "content": "修改成功！"}
                return {"type": "text", "content": "修改失败，请重试。"}
            elif cancel:
                self.reset()
                return {"type": "text", "content": "已取消修改操作。"}
            else:
                return {"type": "text", "content": "请回复确认或取消。"}

        return {"type": "text", "content": "请回复确认或取消。"}

    def _detect_query(self, text: str) -> Optional[dict]:
        """检测查询意图并处理"""
        today = date.today()
        year, month = today.year, today.month

        # 1. 单条记录查询："我哪天买的三体"
        keyword_query = re_match(text, r'(?:哪天|什么时候|何时).*?买[的]?(.+?)(?:\?|？|$)')
        if not keyword_query:
            keyword_query = re_match(text, r'(.+?)是(?:哪天|什么时候|何时)买的')
        if keyword_query:
            keyword = keyword_query.strip().rstrip("?？").strip()
            records = db.search_records(keyword)
            if records:
                r = records[0]
                d = r["record_date"]
                ds = d.strftime("%Y年%m月%d日") if hasattr(d, 'strftime') else str(d)
                amt = abs(r["amount"])
                return {
                    "type": "query_result",
                    "content": f"{ds}购买《{r['item']}》花费{amt:.0f}元"
                }
            return {"type": "query_result", "content": f"没找到关于「{keyword}」的记录。"}

        # 2. 成员支出汇总："这个月女儿花了多少钱"
        for member in FAMILY_MEMBERS:
            if f"这个月{member}花了多少钱" in text or f"本月{member}花了多少钱" in text:
                summary = db.get_monthly_summary(year, month, member=member)
                records = summary["records"]
                if records:
                    total = sum(abs(r["amount"]) for r in records if r["type"] == "支出")
                    items_list = "\n".join(
                        f"  {r['record_date'].strftime('%m月%d日')} {r['category']} {r['item']} {abs(r['amount']):.0f}元"
                        for r in records
                    )
                    return {
                        "type": "query_result",
                        "content": f"根据您提供的信息，这个月{member}的总支出金额为{total:.0f}元，具体支出项目如下：\n{items_list}"
                    }
                return {"type": "query_result", "content": f"本月{member}暂无支出记录。"}

        # 3. 月度分类汇总："我这个月买书花了多少钱"（必须2字以上避免误匹配成员名）
        cat_match = re_match(text, r'(?:这个月|本月).*?(\S{2,}?)花了多少钱')
        if cat_match:
            category = cat_match
            summary = db.get_monthly_summary(year, month, category=category)
            records = summary["records"]
            if records:
                total = sum(abs(r["amount"]) for r in records if r["type"] == "支出")
                count = len(records)
                start = f"{year}年{month}月1日"
                end = f"{year}年{month}月{today.day}日"
                items_list = "\n".join(
                    f"  {r['record_date'].strftime('%m月%d日')} {r['member']} {r['item']} {abs(r['amount']):.0f}元"
                    for r in records
                )
                return {
                    "type": "query_result",
                    "content": f"自{start}至{end}，共{count}笔{category}，共花费{total:.0f}元。\n明细如下：\n{items_list}"
                }
            return {"type": "query_result", "content": f"本月暂无{category}支出。"}

        # 4. 月度明细查询："看下这个月家里花钱明细"
        month_query = any(kw in text for kw in ["这个月", "本月", "明细", "花钱明细", "支出明细"])
        if month_query and ("明细" in text or "花钱" in text or "支出" in text or "账单" in text):
            detail = db.get_monthly_detail(year, month)
            records = detail["records"]
            grouped = detail["grouped"]
            if not records:
                return {"type": "query_result", "content": "本月暂无任何收支记录。"}

            # 按类型汇总
            income_total = sum(r["total"] for r in grouped if r["type"] == "收入")
            expense_total = sum(abs(r["total"]) for r in grouped if r["type"] == "支出")

            result_lines = [f"{year}年{month}月家庭收支明细", "=" * 30]
            result_lines.append(f"总收入: {income_total:.0f}元 | 总支出: {expense_total:.0f}元")
            result_lines.append("")

            result_lines.append("【收入明细】")
            has_income = False
            for g in grouped:
                if g["type"] == "收入":
                    has_income = True
                    result_lines.append(f"  {g['member']} - {g['category']}: {g['total']:.0f}元 ({g['count']}笔)")
            if not has_income:
                result_lines.append("  （无）")

            result_lines.append("")
            result_lines.append("【支出明细】")
            has_expense = False
            for g in grouped:
                if g["type"] == "支出":
                    has_expense = True
                    result_lines.append(f"  {g['member']} - {g['category']}: {abs(g['total']):.0f}元 ({g['count']}笔)")
            if not has_expense:
                result_lines.append("  （无）")

            result_lines.append("")
            result_lines.append("【逐笔记录】")
            for r in records:
                d = r["record_date"]
                ds = d.strftime("%m月%d日") if hasattr(d, 'strftime') else str(d)
                amt_str = f"+{r['amount']:.0f}元" if r["type"] == "收入" else f"{r['amount']:.0f}元"
                result_lines.append(f"  {ds} {r['member']} {r['category']} - {r['item']} {amt_str}")

            return {"type": "query_result", "content": "\n".join(result_lines)}

        # 5. 简化的查询：查某个项目花费
        # "买书花了多少钱", "三体花了多少钱"
        for member in FAMILY_MEMBERS:
            pat = rf"{member}.*?花了多少钱"
            if re_search(text, pat):
                summary = db.get_monthly_summary(year, month, member=member)
                records = summary["records"]
                if records:
                    total = sum(abs(r["amount"]) for r in records if r["type"] == "支出")
                    items_list = "\n".join(
                        f"  {r['record_date'].strftime('%m月%d日')} {r['category']} {r['item']} {abs(r['amount']):.0f}元"
                        for r in records
                    )
                    return {
                        "type": "query_result",
                        "content": f"本月{member}总支出{total:.0f}元，明细如下：\n{items_list}"
                    }
                return {"type": "query_result", "content": f"本月{member}暂无支出记录。"}

        return None

    def _detect_delete(self, text: str) -> Optional[dict]:
        """检测删除意图"""
        if "删除" not in text and "取消" not in text:
            return None

        # 提取删除条件
        text_clean = text.replace("删除", "").strip()

        member = None
        for m in FAMILY_MEMBERS:
            if m in text_clean:
                member = m
                text_clean = text_clean.replace(m, "").strip()
                break

        keyword = text_clean.strip()
        # 去掉一些无意义的词
        for w in ["的", "费用", "记录", "那笔", "那个", "这笔", "这个", "了"]:
            keyword = keyword.replace(w, "").strip()

        if not keyword and not member:
            return {"type": "text", "content": "请提供具体的删除条件，例如「删除女儿的买书记录」。"}

        records = db.delete_records_by_condition(member, "", keyword)

        if not records:
            return {"type": "text", "content": f"未找到符合条件的记录。"}

        # 展示待删除记录
        lines = ["找到以下待删除的记录："]
        for r in records:
            d = r["record_date"]
            ds = d.strftime("%Y年%m月%d日") if hasattr(d, 'strftime') else str(d)
            amt_str = f"+{r['amount']:.0f}元" if r["type"] == "收入" else f"{r['amount']:.0f}元"
            lines.append(f"  [{r['id']}] {ds} {r['member']} {r['category']} - {r['item']} {amt_str}")

        lines.append("")
        lines.append(f"共 {len(records)} 条记录，确认删除吗？（回复确认或取消）")

        self.state = AgentState.PENDING_CONFIRM_DELETE
        self.pending_data = records

        return {"type": "confirm_delete", "content": "\n".join(lines), "data": records}

    def _detect_update(self, text: str) -> Optional[dict]:
        """检测修改意图"""
        if "修改" not in text and "改" not in text and "更正" not in text:
            return None

        # 目前简化处理：检测到修改关键词，引导用户提供要修改的具体内容
        return {"type": "text", "content": "请告诉我您要修改哪条记录以及修改成什么内容？例如「把女儿的买鞋记录改成买书」。"}


def re_match(text: str, pattern: str) -> Optional[str]:
    """正则匹配，返回第一个分组或None"""
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None


def re_search(text: str, pattern: str) -> Optional[re.Match]:
    """正则搜索"""
    return re.search(pattern, text)
