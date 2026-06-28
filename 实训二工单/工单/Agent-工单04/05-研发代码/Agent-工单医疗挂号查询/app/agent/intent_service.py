"""意图识别和槽位抽取。"""

from __future__ import annotations
"""把用户输入的自然语言 query，解析成 Agent 能理解的 intent + slots"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from app.agent.llm_client import LLMClient
from app.common.error_handler import InvalidTimeExpressionError

DEPARTMENTS = ["儿科", "牙科", "眼科", "皮肤科", "消化内科"]
DOCTORS = ["张建国", "儿科专家医生", "牙科医生", "眼科专家医生", "皮肤科医生", "消化内科普通医生"]
PATIENTS = ["本人", "大宝", "二宝"]
CHINESE_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}


@dataclass(slots=True)
class ParsedIntent:
    intent: str
    slots: dict[str, str] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)
    missing_slots: list[str] = field(default_factory=list)


class IntentService:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(self) -> None:
        self.llm_client = LLMClient()

    def parse(self, query: str) -> ParsedIntent:
        llm_result = self.llm_client.extract_intent_and_slots(query)
        if llm_result:
            parsed = ParsedIntent(
                intent=llm_result.get("intent", "unknown"),
                slots={key: value for key, value in llm_result.items() if key != "intent" and value},
                trace=["优先尝试 LLM 解析用户意图与槽位。"],
            )
        else:
            parsed = self._fallback_parse(query)
            parsed.trace.insert(0, "LLM 不可用或返回异常，已切换规则解析 fallback。")
        parsed.missing_slots = self._check_missing_slots(parsed.intent, parsed.slots)
        return parsed

    """槽位抽取  - 意图识别只是知道“要做什么”，槽位抽取是知道“用什么参数做"""
    def _fallback_parse(self, query: str) -> ParsedIntent:
        intent = self._detect_intent(query)
        slots: dict[str, str] = {}

        for patient in PATIENTS:
            if patient in query:
                slots["patient_name"] = patient
                break
        if "patient_name" not in slots: # 抽取患者 patient_name
            patient_match = re.search(r"(本人|[\u4e00-\u9fa5]{1,4}宝)", query)
            if patient_match:
                slots["patient_name"] = patient_match.group(1)

        for department in DEPARTMENTS: # DEPARTMENTS = ["儿科", "牙科", "眼科", "皮肤科", "消化内科"]
            if department in query:
                slots["department_name"] = department
                break
        if "department_name" not in slots: # 抽取科室 department_name
            department_match = re.search(r"([\u4e00-\u9fa5]{1,8}科)", query)
            if department_match:
                slots["department_name"] = department_match.group(1)

        for doctor in DOCTORS:           # DOCTORS = ["张建国", "儿科专家医生", "牙科医生", "眼科专家医生", "皮肤科医生", "消化内科普通医生"]
            if doctor in query:
                slots["doctor_name"] = doctor
                break
        if "doctor_name" not in slots:   # 抽取医生 doctor_name
            doctor_match = re.search(r"([\u4e00-\u9fa5]{2,8}医生)", query)
            if doctor_match:
                slots["doctor_name"] = doctor_match.group(1)

        if "专家" in query:              # 抽取号源类型 slot_type
            slots["slot_type"] = "expert"
        elif "普通号" in query or "普通" in query or (intent == "book_appointment" and "号" in query):
            slots["slot_type"] = "normal"

        date_expr = self._extract_date_expr(query) #抽取日期 date_expr
        if date_expr:
            slots["date_expr"] = date_expr

        time_expr = self._extract_time_expr(query) # 抽取时间 time_expr
        if time_expr:
            slots["time_expr"] = time_expr

        if "之前挂过" in query or "再约那个专家" in query or "再约那个医生" in query:
            slots["history_condition"] = "previous_doctor"

        if intent in {"cancel_appointment", "repeat_previous_doctor"} and "patient_name" not in slots:
            slots["patient_name"] = "本人"

        trace = [f"识别意图：{intent}", f"抽取槽位：{slots}"]
        return ParsedIntent(intent=intent, slots=slots, trace=trace)

    """意图识别 - 把用户一句话归类到某个业务动作"""
    @staticmethod
    def _detect_intent(query: str) -> str:
        if "取消" in query:
            return "cancel_appointment"
        if "坐诊" in query or "排班" in query:
            return "query_doctor_schedule"
        if "之前挂过" in query or "再约那个专家" in query or "再约那个医生" in query:
            return "repeat_previous_doctor"
        if "还有号" in query or "最近的号" in query or "哪天" in query or "查号" in query or "号源" in query:
            return "query_slots"
        if "挂号" in query or "预约" in query or ("挂" in query and "号" in query):
            return "book_appointment"
        return "unknown"

    @staticmethod
    def _extract_date_expr(query: str) -> str | None:
        known = ["今天", "明天", "后天", "下周", "上周三", "最近"]
        for item in known:
            if item in query:
                return item
        match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*(?:日|号)?", query)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"
        match = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", query)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _parse_chinese_number(value: str) -> str:
        if value.isdigit():
            return value
        return str(CHINESE_NUMBERS.get(value, value))

    @staticmethod
    def _extract_time_expr(query: str) -> str | None:
        pattern = re.compile(
            r"(上午|下午|早上|晚上)?\s*(\d{1,2}|十[一二]?|[一二两三四五六七八九十])"
            r"(?:(:|：|点)(\d{1,2}|十[一二]?|[一二两三四五六七八九十]))?\s*(点|分|半)?"
        )
        for match in pattern.finditer(query):
            meridiem = match.group(1) or ""
            separator = match.group(3)
            suffix = match.group(5) or ""
            if not meridiem and not separator and not suffix:
                continue
            hour = IntentService._parse_chinese_number(match.group(2))
            minute = IntentService._parse_chinese_number(match.group(4)) if match.group(4) else None
            if suffix == "半" and minute is None:
                minute = "30"
            if minute and separator in {":", "："}:
                return f"{meridiem}{hour}:{minute}"
            if minute:
                return f"{meridiem}{hour}点{minute}分"
            return f"{meridiem}{hour}点"
        return None

    """缺失槽位"""
    @staticmethod
    def _check_missing_slots(intent: str, slots: dict[str, str]) -> list[str]:
        required_map = {
            "book_appointment": [["patient_name"], ["department_name", "doctor_name"], ["date_expr"], ["time_expr", "slot_type"]],
            "query_slots": [["department_name", "doctor_name"]],
            "cancel_appointment": [["department_name", "doctor_name"], ["date_expr"]],
            "query_doctor_schedule": [["doctor_name"]],
            "repeat_previous_doctor": [["patient_name"]],
        }
        missing: list[str] = []
        for group in required_map.get(intent, []):
            if not any(item in slots and slots[item] for item in group):
                missing.append("/".join(group))
        return missing
    # IntentService.parse() 负责把用户自然语言解析成结构化任务。它先调用 LLMClient 尝试提取 intent 和 slots，如果 LLM 不可用或返回异常，就走 fallback 规则解析。
    # fallback 解析主要通过关键词识别意图，比如“取消”对应 cancel_appointment，“坐诊”对应 query_doctor_schedule，“最近的号/还有号”对应 query_slots，“挂号/预约”对应 book_appointment。
    # 槽位抽取则从用户 query 中提取患者、科室、医生、日期、时间和号源类型。比如“大宝”会抽成 patient_name，“儿科”会抽成 department_name，“专家号”会抽成 slot_type=expert，“今天下午2点”会抽成 date_expr=今天、time_expr=下午2点。
    # 解析完成后，系统还会检查当前意图所需的必要槽位是否完整。如果缺少关键信息，就返回 missing_slots，后续 AgentService 会进入 NEED_INFO，而不是直接调用工具。

def resolve_date_filters(date_expr: str | None, today: date | None = None) -> tuple[date | None, date | None, date | None]:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    today = today or date.today()
    if not date_expr:
        return today, today + timedelta(days=30), None
    if date_expr == "今天":
        return today, today, today
    if date_expr == "明天":
        target = today + timedelta(days=1)
        return target, target, target
    if date_expr == "后天":
        target = today + timedelta(days=2)
        return target, target, target
    if date_expr == "最近":
        return today, today + timedelta(days=7), None
    if date_expr == "下周":
        days_to_next_monday = (7 - today.weekday()) or 7
        start = today + timedelta(days=days_to_next_monday)
        end = start + timedelta(days=6)
        return start, end, None
    if date_expr == "上周三":
        current_week_wednesday = today - timedelta(days=today.weekday() - 2)
        target = current_week_wednesday - timedelta(days=7)
        return target, target, target
    try:
        target = datetime.strptime(date_expr, "%Y-%m-%d").date()
        return target, target, target
    except ValueError as exc:
        raise InvalidTimeExpressionError("时间信息不够明确，请补充具体日期和时间。", code="INVALID_DATE_EXPR") from exc


def resolve_time_value(time_expr: str | None) -> time | None:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    if not time_expr:
        return None
    text = time_expr.replace(" ", "")
    meridiem = ""
    if text.startswith(("上午", "早上")):
        meridiem = "上午"
    elif text.startswith(("下午", "晚上")):
        meridiem = "下午"
    text = text.removeprefix("上午").removeprefix("早上").removeprefix("下午").removeprefix("晚上")
    match = re.match(r"(\d{1,2})(?::|点)?(\d{1,2})?(?:分)?", text)
    if not match:
        raise InvalidTimeExpressionError("时间信息不够明确，请补充具体日期和时间。", code="INVALID_TIME_EXPR")
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if "半" in time_expr:
        minute = 30
    if meridiem == "下午" and hour < 12:
        hour += 12
    if meridiem == "上午" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        raise InvalidTimeExpressionError("时间信息不够明确，请补充具体日期和时间。", code="INVALID_TIME_EXPR")
    return time(hour=hour, minute=minute)
