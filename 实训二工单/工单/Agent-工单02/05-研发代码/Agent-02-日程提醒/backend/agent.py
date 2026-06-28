"""
日程管家 - Agent 核心引擎
工单：人工智能 NLP-Agent 数字人项目-日程管家任务

工作流程：
1. 接收用户自然语言输入
2. LLM 解析为结构化意图（含时间和内容）
3. 按状态机处理：信息采集 → 循环询问 → 确认 → 执行
4. 每次操作后返回结果+当前日程列表
"""

import datetime
import json
import logging
import random
import re
from typing import Any

import httpx

from config import SETTINGS
from database import (
    add_schedule,
    delete_schedule,
    get_due_schedules,
    get_schedule_by_id,
    query_schedules,
    update_schedule,
)

logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================================
# 4 种温馨提醒句式（工单要求）
# ============================================================
REMINDER_TEMPLATES = [
    "温馨提醒：{content}的时间到啦，主人！",
    "主人！是时候{content}了喔~",
    "亲爱的主人，现在是{content}的时候啦！",
    "嘿，主人，该{content}了哦~",
]

# ============================================================
# 系统 Prompt（定义「日程管家」角色）
# ============================================================
SYSTEM_PROMPT = """你是「日程管家」，一个专精于日程管理的智能助手。

当前服务器时间：{current_datetime}

## 核心职责
帮助用户管理日程，严格按以下规则操作。

## 支持的 Intent
1. add：添加日程
2. query：查询日程
3. delete：删除日程（必须先 query 获取编号）
4. modify：修改日程
5. confirm：用户确认操作
6. cancel：用户取消操作
7. prompt：信息不完整，要求用户补充
8. chat：普通闲聊/问候

## 字段说明
- content：日程事项内容（如"开会""买咖啡""起床"）
- event_time：提醒时间，格式 YYYY-MM-DD HH:MM（如 "2026-06-14 17:00"）
- repeat_rule：循环规则，""(一次性) / "每天" / "工作日" / "每周一" / "每周一,三,五"
- schedule_id：日程编号
- modified_fields：修改操作中要更新的字段

## 时间解析规则
- "下午5点" → 当天 17:00
- "明天早上8点" → 明天 08:00
- "半小时后" → 当前时间+30分钟
- "过一会儿" → 当前时间+15分钟
- "后天下午3点" → 后天 15:00
- "每周一早上9点开会" → intent:add, content:"开会", event_time:"下周一的09:00", repeat_rule:"每周一"

## 交互规则（必须遵守）
1. 添加：必须提取内容+时间，如缺少任一字段 → intent:prompt，指出缺失字段
2. 删除：要求用户提供编号，如没有编号 → intent:prompt
3. 修改：要求提供编号+修改内容，如缺少 → intent:prompt
4. 查询：支持"今天""明天""本周"等模糊时间
5. 所有操作完成后必须返回日程列表

## 输出 JSON（只输出 JSON，不要 markdown 代码块）
{{
  "intent": "add/query/delete/modify/confirm/cancel/prompt/chat",
  "content": "",
  "event_time": "",
  "repeat_rule": "",
  "schedule_id": 0,
  "filters": {{
    "date_from": "",
    "date_to": "",
    "status": ""
  }},
  "message": "",
  "missing_fields": [],
  "modified_fields": {{}}
}}

## 示例
用户："明天下午3点开会"
→ {{"intent":"add", "content":"开会", "event_time":"2026-06-14 15:00", "repeat_rule":"", ...}}

用户："每天早上8点提醒我起床"
→ {{"intent":"add", "content":"起床", "event_time":"2026-06-13 08:00", "repeat_rule":"每天", ...}}

用户："看看今天有什么安排"
→ {{"intent":"query", "filters":{{"date_from":"2026-06-13 00:00:00", "date_to":"2026-06-13 23:59:59"}}, ...}}

用户："删除日程1"
→ {{"intent":"delete", "schedule_id":1, ...}}

用户："修改日程1的时间到明天下午4点"
→ {{"intent":"modify", "schedule_id":1, "modified_fields":{{"event_time":"2026-06-14 16:00"}}, ...}}
"""


# ============================================================
# 状态常量
# ============================================================
STATE_IDLE = "idle"
STATE_AWAITING_REPEAT = "awaiting_repeat"       # 等待用户选择循环规则
STATE_AWAITING_CONFIRM_ADD = "awaiting_confirm_add"  # 等待确认添加
STATE_AWAITING_CONFIRM_DELETE = "awaiting_confirm_delete"
STATE_AWAITING_CONFIRM_MODIFY = "awaiting_confirm_modify"
STATE_AWAITING_DELETE_ID = "awaiting_delete_id"  # 缺少编号，等待用户提供
STATE_AWAITING_MODIFY_INFO = "awaiting_modify_info"

SESSION_PREFIX = "__SCHEDULE_STATE__:"


# ============================================================
# 工具函数
# ============================================================

def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _today_str() -> str:
    return _now().strftime(DATE_FORMAT)


def _format_event_time(dt_str: str) -> str:
    """将 YYYY-MM-DD HH:MM:SS 格式化为 MM月DD日 HH:MM"""
    try:
        dt = datetime.datetime.strptime(dt_str[:16], "%Y-%m-%d %H:%M")
        return dt.strftime("%m月%d日 %H:%M")
    except ValueError:
        return dt_str


def _parse_chinese_datetime(text: str) -> str | None:
    """解析中文时间表达，返回 YYYY-MM-DD HH:MM:SS 格式，失败返回 None"""
    now = _now()
    today = now.strftime(DATE_FORMAT)

    # 先确定日期基准
    date_str = today
    if "后天" in text:
        date_obj = now + datetime.timedelta(days=2)
        date_str = date_obj.strftime(DATE_FORMAT)
    elif "明天" in text or "明日" in text:
        date_obj = now + datetime.timedelta(days=1)
        date_str = date_obj.strftime(DATE_FORMAT)
    elif "今天" in text or "今日" in text:
        date_str = today
    elif "大后天" in text:
        date_obj = now + datetime.timedelta(days=3)
        date_str = date_obj.strftime(DATE_FORMAT)

    # 相对时间：半小时后 / 一小时后 / 过一会儿
    if "半小时后" in text:
        dt = now + datetime.timedelta(minutes=30)
        return dt.strftime(DATETIME_FORMAT)
    if "一小时后" in text or "1小时后" in text:
        dt = now + datetime.timedelta(hours=1)
        return dt.strftime(DATETIME_FORMAT)
    if "过一会儿" in text:
        dt = now + datetime.timedelta(minutes=30)
        return dt.strftime(DATETIME_FORMAT)
    if "一会儿" in text or "过会" in text:
        dt = now + datetime.timedelta(minutes=30)
        return dt.strftime(DATETIME_FORMAT)

    # 解析具体时间：早上/下午/晚上 X点(Y分)
    hour = None
    minute = 0
    ampm = None  # None=不指定, "早上"/"上午", "下午", "晚上"

    # 提取上午/下午/早上/晚上/中午
    if "早上" in text or "早晨" in text or "上午" in text:
        ampm = "morning"
    elif "下午" in text:
        ampm = "afternoon"
    elif "晚上" in text:
        ampm = "evening"
    elif "中午" in text:
        ampm = "noon"
    elif "半夜" in text or "凌晨" in text:
        ampm = "night"

    # 提取小时: "5点" "8点" "13点"
    hour_match = re.search(r"(\d+)\s*点", text)
    if hour_match:
        hour = int(hour_match.group(1))
    else:
        # "5时"
        hour_match = re.search(r"(\d+)\s*时", text)
        if hour_match:
            hour = int(hour_match.group(1))

    if hour is None:
        return None

    # 提取分钟: "30分" "半"
    minute_match = re.search(r"(\d+)\s*分", text)
    if minute_match:
        minute = int(minute_match.group(1))
    elif "半" in text:
        minute = 30
    elif "一刻" in text:
        minute = 15
    elif "三刻" in text:
        minute = 45

    # 处理上午/下午
    if ampm == "afternoon" and hour < 12:
        hour += 12
    elif ampm == "evening" and hour < 12:
        hour += 12
    elif ampm == "night" and hour < 12:
        # 凌晨 0-5点保持原样
        if hour >= 5:
            pass  # 保持原样
    elif ampm == "noon":
        if hour < 12:
            pass  # 中午12点左右保持
    elif ampm == "morning":
        pass  # 上午保持

    # 24小时制直接使用
    try:
        result_dt = datetime.datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}:00", DATETIME_FORMAT)
        return result_dt.strftime(DATETIME_FORMAT)
    except ValueError:
        return None


def _get_reminder_text(content: str) -> str:
    """随机选择一句温馨提醒"""
    template = random.choice(REMINDER_TEMPLATES)
    return template.format(content=content)


def _format_schedule_list(schedules: list[dict[str, Any]], title: str = "📋 当前日程") -> str:
    """将日程列表格式化为工单要求的格式：时间|编号|内容"""
    if not schedules:
        return "📭 暂无日程安排。"
    lines = [f"{title}："]
    for s in schedules:
        time_str = s["event_time"][11:16] if len(s["event_time"]) >= 16 else s["event_time"]
        sid = f"{s['id']:07d}"
        content = s["content"]
        repeat = f" 🔄 {s['repeat_rule']}" if s.get("repeat_rule") else ""
        status_icon = "✅" if s["status"] == "completed" else "❌" if s["status"] == "cancelled" else ""
        lines.append(f"  {time_str}|{sid}|{content}{repeat} {status_icon}")
    return "\n".join(lines)


def _get_today_schedules() -> list[dict[str, Any]]:
    """获取今天的日程列表"""
    today = _today_str()
    return query_schedules({
        "date_from": f"{today} 00:00:00",
        "date_to": f"{today} 23:59:59",
    })


def _get_today_str() -> str:
    return _format_event_time(_now().strftime(DATETIME_FORMAT))


# ============================================================
# LLM 调用
# ============================================================

def _build_system_prompt() -> str:
    return SYSTEM_PROMPT.format(
        current_datetime=_now().strftime(DATETIME_FORMAT)
    )


def _build_messages(user_input: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": _build_system_prompt()}]
    # 过滤掉前面 session 状态标记
    clean_history = [m for m in history[-8:] if not m.get("content", "").startswith(SESSION_PREFIX)]
    for msg in clean_history:
        messages.append(msg)
    messages.append({"role": "user", "content": user_input})
    return messages


def _call_llm(messages: list[dict[str, str]]) -> str | None:
    if not SETTINGS.llm_api_key:
        logger.warning("LLM API Key 未配置，跳过模型解析")
        return None

    headers = {
        "Authorization": f"Bearer {SETTINGS.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": SETTINGS.llm_model_name,
        "messages": messages,
        "temperature": SETTINGS.llm_temperature,
        "max_tokens": SETTINGS.llm_max_tokens,
        "top_p": SETTINGS.llm_top_p,
    }

    try:
        with httpx.Client(timeout=SETTINGS.llm_timeout) as client:
            response = client.post(
                f"{SETTINGS.llm_api_base}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            logger.info("LLM 响应: %s", content[:200])
            return content
    except Exception as exc:
        logger.error("LLM 调用失败: %s", exc)
        return None


def _parse_llm_response(content: str) -> dict[str, Any]:
    content_clean = content.strip()
    content_clean = re.sub(r"^```(?:json)?\s*", "", content_clean)
    content_clean = re.sub(r"\s*```$", "", content_clean)
    try:
        result = json.loads(content_clean)
        if not isinstance(result, dict):
            return {"intent": "chat", "message": "我没能理解您的意思，请重新描述一下 🙏"}
        return result
    except json.JSONDecodeError:
        logger.warning("LLM 返回非 JSON: %s", content[:100])
        return {"intent": "chat", "message": content_clean}


# ============================================================
# 规则兜底解析（无 LLM 时）
# ============================================================

def _rule_based_parse(user_input: str) -> dict[str, Any]:
    """快速规则判断，用于无 LLM 时的兜底"""
    text = user_input.strip()
    now = _now()
    today = _today_str()

    greeting_keywords = {"你好", "您好", "hello", "hi", "嗨", "在吗", "谢谢", "感谢", "早安", "晚安"}
    normalized = text.lower().replace("，", "").replace("。", "").replace("？", "").replace("!", "").replace("！", "")
    if normalized in greeting_keywords:
        return {"intent": "chat", "message": "您好！我是「日程管家」，专精于日程管理的智能助手！我可以帮您：\n• 添加日程 — 「明天下午5点提醒我开会」\n• 查询日程 — 「看看我今天有什么安排」\n• 删除日程 — 「删除日程1」\n• 修改日程 — 「把日程1改到明天下午3点」\n请告诉我您的需求吧~"}

    # 删除/修改
    for kw in ["删除", "删掉", "移除", "去掉", "取消"]:
        if kw in text:
            m = re.search(r"(?:日程|编号|#)?\s*(\d+)", text)
            if m:
                return {"intent": "delete", "schedule_id": int(m.group(1))}
            return {"intent": "prompt", "message": "请提供要删除的日程编号，例如「删除日程1」", "missing_fields": ["schedule_id"]}

    for kw in ["修改", "改成", "改到", "改为", "更新", "变更", "推迟", "提前"]:
        if kw in text:
            m = re.search(r"(?:日程|编号|#)?\s*(\d+)", text)
            if m:
                return {"intent": "modify", "schedule_id": int(m.group(1)), "message": text}
            return {"intent": "prompt", "message": "请提供要修改的日程编号，例如「修改日程1的时间到明天下午3点」", "missing_fields": ["schedule_id"]}

    # 查询
    if any(kw in text for kw in ["查看", "看看", "查询", "显示", "什么", "哪些", "今天有", "明天有", "本周有"]):
        result = {"intent": "query", "filters": {}}
        if "今天" in text:
            result["filters"]["date_from"] = f"{today} 00:00:00"
            result["filters"]["date_to"] = f"{today} 23:59:59"
        elif "明天" in text:
            tomorrow = (now + datetime.timedelta(days=1)).strftime(DATE_FORMAT)
            result["filters"]["date_from"] = f"{tomorrow} 00:00:00"
            result["filters"]["date_to"] = f"{tomorrow} 23:59:59"
        elif "本周" in text or "这周" in text:
            monday = now - datetime.timedelta(days=now.weekday())
            sunday = monday + datetime.timedelta(days=6)
            result["filters"]["date_from"] = f"{monday.strftime(DATE_FORMAT)} 00:00:00"
            result["filters"]["date_to"] = f"{sunday.strftime(DATE_FORMAT)} 23:59:59"
        else:
            result["filters"]["date_from"] = f"{today} 00:00:00"
            result["filters"]["date_to"] = f"{today} 23:59:59"
        return result

    # 添加 — 提取时间和内容
    event_time = _parse_chinese_datetime(text)
    has_time = any(kw in text for kw in ["点", "分", "小时", "分钟", "今天", "明天", "后天", "早上", "下午", "晚上", "中午", "半小时", "一会儿"])

    if has_time or any(kw in text for kw in ["提醒", "提醒我", "安排", "预约", "定个", "记一下", "加一个"]):
        # 提取内容：去掉时间关键词和提醒关键词
        content = text
        for kw in ["提醒我", "提醒", "记一下", "安排", "预约", "定个", "加一个"]:
            content = content.replace(kw, "")
        # 去掉介词和时间段词
        for kw in ["明天", "后天", "今天", "早上", "下午", "晚上", "中午", "凌晨", "点", "点半", "分", "分钟", "小时", "半小时", "一会儿", "后"]:
            content = content.replace(kw, "")
        # 去掉数字和冒号
        content = re.sub(r"\d+", "", content)
        content = content.replace(":", "").replace("：", "")
        content = content.strip("，。,.！!？?、")
        if not content:
            # 如果提取后为空，用原文中非时间部分
            content = text
            for kw in ["提醒我", "提醒", "记一下", "安排", "预约", "定个", "加一个"]:
                content = content.replace(kw, "")
            content = content.strip("，。,.！!？?、")
            if not content:
                content = text

        return {"intent": "add", "content": content, "event_time": event_time or ""}

    return {"intent": "chat", "message": "请告诉我您的日程需求，例如「明天下午5点提醒我开会」或「看看我今天有什么安排」😊"}


# ============================================================
# 状态管理 & 会话状态提取/保存
# ============================================================

def _save_session_state(history: list[dict[str, str]], state: dict[str, Any]) -> list[dict[str, str]]:
    """将对话状态保存到 history 中"""
    serialized = json.dumps(state, ensure_ascii=False)
    new_history = list(history)
    new_history.append({"role": "assistant", "content": f"{SESSION_PREFIX}{serialized}"})
    return new_history


def _load_session_state(history: list[dict[str, str]]) -> dict[str, Any] | None:
    """从 history 中提取对话状态"""
    for msg in reversed(history):
        content = msg.get("content", "")
        if content.startswith(SESSION_PREFIX):
            try:
                return json.loads(content[len(SESSION_PREFIX):])
            except (json.JSONDecodeError, ValueError):
                return None
    return None


def _clear_session_state(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """清理会话状态标记"""
    return [m for m in history if not m.get("content", "").startswith(SESSION_PREFIX)]


# ============================================================
# 主处理函数
# ============================================================

def process_schedule_message(
    user_input: str,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    """
    处理用户消息，返回回复
    返回格式：{"reply": str, "history": list, "reminder": str | None}
    """
    logger.info("用户输入: %s", user_input)
    text = user_input.strip()

    # 1. 检查是否有待处理的会话状态
    session_state = _load_session_state(history)
    history_no_state = _clear_session_state(history)
    pending_add = None
    pending_delete = None
    pending_modify = None
    awaiting_repeat = False

    if session_state:
        state = session_state.get("state", STATE_IDLE)
        if state == STATE_AWAITING_REPEAT:
            pending_add = session_state.get("pending_add")
            awaiting_repeat = True
        elif state == STATE_AWAITING_CONFIRM_ADD:
            pending_add = session_state.get("pending_add")
        elif state == STATE_AWAITING_CONFIRM_DELETE:
            pending_delete = session_state.get("pending_delete")
        elif state == STATE_AWAITING_CONFIRM_MODIFY:
            pending_modify = session_state.get("pending_modify")

    # 2. 处理确认/取消操作（使用子串匹配，支持更自然的表达）
    def _is_confirm(text: str) -> bool:
        exact = {"确认", "确认添加", "确认删除", "确认修改", "是的", "对", "好的", "可以", "行", "嗯", "删吧"}
        if text in exact:
            return True
        for kw in ["确认可以", "确认无误", "没问题"]:
            if kw in text:
                return True
        return False

    def _is_cancel(text: str) -> bool:
        exact = {"取消", "算了", "不", "否"}
        if text in exact:
            return True
        for kw in ["不需要", "不用了", "不要了", "不删了", "别删了", "不修改", "不添加", "取消添加", "取消删除", "取消修改", "不设置", "不要循环", "不需要循环"]:
            if kw in text:
                return True
        return False

    normalized_input = text.replace("，", "").replace("。", "").replace("！", "").replace("？", "").strip().lower()

    # 处理添加确认
    if pending_add and _is_confirm(normalized_input):
        return _execute_add(pending_add, history)

    # 处理删除确认
    if pending_delete and _is_confirm(normalized_input):
        return _execute_delete(pending_delete, history)

    # 处理修改确认
    if pending_modify and _is_confirm(normalized_input):
        return _execute_modify(pending_modify, history)

    # 处理取消
    if _is_cancel(normalized_input):
        return {"reply": "已取消操作。还有什么需要帮忙的吗？😊", "history": history_no_state}

    # 处理循环规则回复（如果在等待循环输入）
    if awaiting_repeat and pending_add:
        repeat_rule = _parse_repeat_rule(text)
        if repeat_rule is not None:
            # 用户明确说了循环规则，进入确认环节
            pending_add["repeat_rule"] = repeat_rule
            return _show_add_confirm(pending_add, history_no_state)
        elif _is_repeat_response(text):
            # 用户回答了循环（但不标准），默认按用户说的来
            pending_add["repeat_rule"] = text
            return _show_add_confirm(pending_add, history_no_state)
        else:
            # 用户没有回答循环规则（说了别的内容），默认不循环，直接保存
            # 然后重新处理当前输入
            try:
                _execute_add_auto(pending_add)
            except Exception as e:
                logger.error("自动保存失败: %s", e)
            # 清除状态，重新处理当前输入
            return process_schedule_message(text, history_no_state)

    # 3. 处理删除请求 — 需要编号
    delete_match = re.search(r"(?:删除|删掉|移除|去掉|取消)\s*(?:日程|编号|#)?\s*(\d+)", text)
    if delete_match:
        sid = int(delete_match.group(1))
        schedule = get_schedule_by_id(sid)
        if not schedule:
            return {"reply": f"⚠️ 未找到编号为 {sid} 的日程，请确认编号是否正确。", "history": history_no_state}
        # 确认环节
        confirm_msg = (
            f"即将删除日程{sid}：{schedule['event_time'][11:16]} {schedule['content']}，确认吗？"
        )
        new_history = _save_session_state(history_no_state, {
            "state": STATE_AWAITING_CONFIRM_DELETE,
            "pending_delete": {"schedule_id": sid, "content": schedule["content"], "time": schedule["event_time"][11:16]},
        })
        return {"reply": confirm_msg, "history": new_history}

    # 4. 处理修改请求
    modify_match = re.search(r"(?:修改|改成|改到|改为|更新|变更|推迟|提前)\s*(?:日程|编号|#)?\s*(\d+)", text)
    if modify_match:
        sid = int(modify_match.group(1))
        schedule = get_schedule_by_id(sid)
        if not schedule:
            return {"reply": f"⚠️ 未找到编号为 {sid} 的日程，请确认编号是否正确。", "history": history_no_state}
        # 提取要修改的内容
        modified_fields = _extract_modify_fields(text, schedule)
        if not modified_fields:
            return {"reply": f"请告诉我您想修改日程{sid}的什么内容？例如「修改日程{sid}的时间到明天下午4点」", "history": history_no_state}

        confirm_msg_parts = [f"即将修改日程{sid}"]
        for field, value in modified_fields.items():
            if field == "event_time":
                confirm_msg_parts.append(f"时间改为：{_format_event_time(value)}")
            elif field == "content":
                confirm_msg_parts.append(f"内容改为：{value}")
            elif field == "repeat_rule":
                confirm_msg_parts.append(f"循环改为：{value or '无'}")

        new_history = _save_session_state(history_no_state, {
            "state": STATE_AWAITING_CONFIRM_MODIFY,
            "pending_modify": {"schedule_id": sid, "modified_fields": modified_fields},
        })
        return {"reply": "，".join(confirm_msg_parts) + "，确认吗？", "history": new_history}

    # 5. LLM 解析（主要方式）
    messages = _build_messages(text, history_no_state)
    llm_response = _call_llm(messages)
    if llm_response:
        parsed = _parse_llm_response(llm_response)
        intent = parsed.get("intent", "chat")
    else:
        parsed = _rule_based_parse(text)
        intent = parsed.get("intent", "chat")

    logger.info("意图解析: intent=%s", intent)

    # 6. 按意图处理
    if intent == "chat":
        return {"reply": parsed.get("message", "您好！我是「日程管家」！请问有什么需要帮您的吗？😊"), "history": history_no_state}

    if intent == "add":
        return _handle_add(parsed, history_no_state)

    if intent == "query":
        return _handle_query(parsed)

    if intent == "delete":
        # LLM 返回了 delete 但可能没有编号
        sid = parsed.get("schedule_id", 0)
        if sid:
            schedule = get_schedule_by_id(sid)
            if not schedule:
                return {"reply": f"⚠️ 未找到编号为 {sid} 的日程。", "history": history_no_state}
            confirm_msg = (
                f"即将删除日程{sid}：{schedule['event_time'][11:16]} {schedule['content']}，确认吗？"
            )
            new_history = _save_session_state(history_no_state, {
                "state": STATE_AWAITING_CONFIRM_DELETE,
                "pending_delete": {"schedule_id": sid, "content": schedule["content"], "time": schedule["event_time"][11:16]},
            })
            return {"reply": confirm_msg, "history": new_history}
        else:
            return {"reply": "请提供要删除的日程编号，例如「删除日程1」", "history": history_no_state}

    if intent == "modify":
        sid = parsed.get("schedule_id", 0)
        if not sid:
            return {"reply": "请提供要修改的日程编号，例如「修改日程1的时间到明天下午4点」", "history": history_no_state}
        schedule = get_schedule_by_id(sid)
        if not schedule:
            return {"reply": f"⚠️ 未找到编号为 {sid} 的日程。", "history": history_no_state}
        modified = parsed.get("modified_fields", {})
        if not modified:
            return {"reply": f"请告诉我您想修改日程{sid}的什么内容？", "history": history_no_state}
        confirm_parts = [f"即将修改日程{sid}"]
        for field, value in modified.items():
            if field == "event_time":
                confirm_parts.append(f"时间改为：{_format_event_time(value)}")
            elif field == "content":
                confirm_parts.append(f"内容改为：{value}")
            elif field == "repeat_rule":
                confirm_parts.append(f"循环改为：{value or '无'}")
        new_history = _save_session_state(history_no_state, {
            "state": STATE_AWAITING_CONFIRM_MODIFY,
            "pending_modify": {"schedule_id": sid, "modified_fields": modified},
        })
        return {"reply": "，".join(confirm_parts) + "，确认吗？", "history": new_history}

    if intent == "prompt":
        msg = parsed.get("message", "信息不完整，请补充。")
        return {"reply": msg, "history": history_no_state}

    # 兜底
    return {"reply": "抱歉，我没能理解您的意思，请重新描述一下吧 🙏", "history": history_no_state}


# ============================================================
# 添加日程处理
# ============================================================

def _handle_add(parsed: dict[str, Any], history: list[dict[str, str]]) -> dict[str, Any]:
    """处理添加日程"""
    content = parsed.get("content", "").strip()
    event_time = parsed.get("event_time", "").strip()
    repeat_rule = parsed.get("repeat_rule", "").strip()

    # 检查缺少字段
    missing = []
    if not content:
        missing.append("content")
    if not event_time:
        missing.append("event_time")

    if missing:
        field_labels = {
            "content": "⚠️ 请告诉我日程事项内容（如：开会、买咖啡、起床）",
            "event_time": "⚠️ 请告诉我具体时间（如：下午5点、明天早上8点）",
        }
        details = "\n".join(field_labels.get(f, f"⚠️ 缺少：{f}") for f in missing)
        return {"reply": f"信息还不完整，请补充以下内容：\n{details}", "history": history}

    pending_data = {"content": content, "event_time": event_time, "repeat_rule": ""}

    # 如果 LLM 已经解析了循环规则，直接进确认
    if repeat_rule:
        pending_data["repeat_rule"] = repeat_rule
        return _show_add_confirm(pending_data, history)

    # 否则直接进入确认（不再询问循环规则）
    display_time = _format_event_time(event_time)
    return _show_add_confirm(pending_data, history)


def _parse_repeat_rule(text: str) -> str | None:
    """解析用户说的循环规则"""
    t = text.strip()
    # 不循环 / 不需要循环 / 不要循环
    if t in ["不循环", "不设置", "不用", "没有", "无", "一次性", "否", "不要"]:
        return ""
    if "不" in t and ("循环" in t or "重复" in t):
        return ""
    # 每天
    if t in ["每天", "每日", "天天", "每日一次", "一天一次"]:
        return "每天"
    # 工作日
    if t in ["工作日", "工作日重复", "周一至周五", "周一到周五", "工作日每天"]:
        return "工作日"
    # 每周X
    weekday_match = re.search(r"每周[的周]?([一二三四五六日1-7,，、]+)", t)
    if weekday_match:
        day_str = weekday_match.group(1)
        # 转换中文数字
        day_mapping = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5", "六": "6", "日": "7"}
        result_parts = []
        for ch in day_str:
            if ch in day_mapping:
                result_parts.append(day_mapping[ch])
            elif ch.isdigit():
                result_parts.append(ch)
        if result_parts:
            return "每周" + ",".join(result_parts)
        return t
    # 模糊匹配：用户说了"循环"/"重复"但没有具体规则 → 默认每天
    if "循环" in t or "重复" in t or t in ["你循环", "循环一下", "要循环"]:
        return "每天"
    return None


def _is_repeat_response(text: str) -> bool:
    """判断用户是否在回复循环规则"""
    t = text.strip()
    keywords = ["每天", "每日", "工作日", "每周", "周", "循环", "重复", "不循环", "不设置", "一次性", "不用", "星期"]
    return any(kw in t for kw in keywords)


def _show_add_confirm(pending_data: dict[str, Any], history: list[dict[str, str]]) -> dict[str, Any]:
    """展示添加确认信息"""
    display_time = _format_event_time(pending_data["event_time"])
    repeat_display = pending_data["repeat_rule"] if pending_data["repeat_rule"] else "无（一次性）"
    repeat_text = f"，循环规则：{pending_data['repeat_rule']}" if pending_data["repeat_rule"] else ""

    new_history = _save_session_state(history, {
        "state": STATE_AWAITING_CONFIRM_ADD,
        "pending_add": pending_data,
    })

    confirm_msg = (
        f"即将为您添加日程：\n"
        f"📅 {display_time}，📝 {pending_data['content']}{repeat_text}\n"
        f"确认吗？（回复「确认」或「取消」）"
    )
    return {"reply": confirm_msg, "history": new_history}


def _execute_add_auto(pending_data: dict[str, Any]) -> None:
    """自动保存（不循环，无需用户确认）"""
    schedule_id = add_schedule(
        content=pending_data["content"],
        event_time=pending_data["event_time"],
        repeat_rule="",
    )
    logger.info("✅ 自动保存（无循环）id=%s: %s", schedule_id, pending_data)


def _execute_add(pending_data: dict[str, Any], history: list[dict[str, str]]) -> dict[str, Any]:
    """执行添加操作"""
    try:
        schedule_id = add_schedule(
            content=pending_data["content"],
            event_time=pending_data["event_time"],
            repeat_rule=pending_data["repeat_rule"],
        )
        logger.info("✅ 添加日程成功 id=%s", schedule_id)

        # 返回添加成功 + 当天日程
        today_schedules = _get_today_schedules()
        schedule_list = _format_schedule_list(today_schedules, "已添加成功！当前日程如下")

        reply = f"已添加成功！✅\n"
        if today_schedules:
            reply += schedule_list
        else:
            reply += f"已为您添加：{_format_event_time(pending_data['event_time'])} {pending_data['content']}"
            if pending_data.get("repeat_rule"):
                reply += f"（循环：{pending_data['repeat_rule']}）"

        return {
            "reply": reply,
            "history": _clear_session_state(history),
        }
    except Exception as e:
        logger.error("添加日程失败: %s", e)
        return {"reply": f"❌ 添加日程失败：{str(e)}", "history": history}


# ============================================================
# 查询日程处理
# ============================================================

def _handle_query(parsed: dict[str, Any]) -> dict[str, Any]:
    """处理查询日程"""
    filters = parsed.get("filters", {})

    # 如果 LLM 没解析出时间范围，默认查今天
    if not filters.get("date_from") and not filters.get("date_to"):
        today = _today_str()
        filters["date_from"] = f"{today} 00:00:00"
        filters["date_to"] = f"{today} 23:59:59"

    schedules = query_schedules(filters)
    return {"reply": _format_schedule_list(schedules), "history": None}


# ============================================================
# 删除日程处理
# ============================================================

def _execute_delete(pending_delete: dict[str, Any], history: list[dict[str, str]]) -> dict[str, Any]:
    """执行删除操作"""
    sid = pending_delete["schedule_id"]
    content = pending_delete.get("content", "")
    time_str = pending_delete.get("time", "")

    logger.info("执行删除日程 id=%s", sid)
    success = delete_schedule(sid)

    if success:
        return {
            "reply": f"已删除日程{sid}，删除的日程内容是：{time_str} {content}",
            "history": _clear_session_state(history),
        }
    else:
        return {"reply": f"⚠️ 删除日程{sid}失败，请稍后重试。", "history": history}


# ============================================================
# 修改日程处理
# ============================================================

def _extract_modify_fields(text: str, current_schedule: dict[str, Any]) -> dict[str, Any]:
    """从用户输入中提取要修改的字段"""
    fields = {}

    # 提取新时间
    time_patterns = [
        (r"(?:改到|改成|改为|提前|推迟)\s*(?:明天|后天|今天|下周一|下周二|下周三|下周四|下周五|下周六|下周日|下周[一二三四五六日])?\s*(?:早上|下午|晚上|中午)?\s*(\d+)\s*(?:[:：点])\s*(\d+)?\s*(?:分)?", True),
        (r"(?:改到|改成|改为|提前|推迟)\s*(?:明天|后天|今天)\s*(?:早上|下午|晚上|中午)?\s*(\d+)\s*[:：点时]\s*(\d+)?", True),
    ]

    # 提取新内容
    content_patterns = [
        r"(?:内容改为|改成|修改为)\s*[「『]?(.+?)[」』]?(?:\s|$|，|。)",
        r"(?:改为|改成)\s*[「『](.+?)[」』]",
    ]

    for pattern, is_time in time_patterns:
        m = re.search(pattern, text)
        if m:
            # 简单处理：调 LLM 或规则解析时间
            # 这里先不做复杂时间解析，让 LLM 处理
            pass

    # 检查是否提到"时间"
    if any(kw in text for kw in ["时间", "点", "分", "推迟", "提前", "改到"]):
        # 让 LLM 处理时间解析，这里标记需要修改时间
        pass

    # 检查是否提到"内容"
    for pattern in content_patterns:
        m = re.search(pattern, text)
        if m:
            fields["content"] = m.group(1).strip()
            break

    # 检查是否提到"循环"
    if "循环" in text or "重复" in text:
        for kw in ["每天", "日日", "工作日", "每周"]:
            if kw in text:
                fields["repeat_rule"] = kw
                break

    # 检查是否提到"取消循环"
    if "取消循环" in text or "取消重复" in text or "不循环" in text:
        fields["repeat_rule"] = ""

    return fields


def _execute_modify(pending_modify: dict[str, Any], history: list[dict[str, str]]) -> dict[str, Any]:
    """执行修改操作"""
    sid = pending_modify["schedule_id"]
    modified_fields = pending_modify["modified_fields"]

    logger.info("执行修改日程 id=%s: %s", sid, modified_fields)
    success = update_schedule(sid, **modified_fields)

    if success:
        updated = get_schedule_by_id(sid)
        parts = [f"✅ 已成功修改日程{sid}"]
        if updated:
            parts.append(f"当前内容：{updated['event_time'][11:16]} {updated['content']}")
            if updated.get("repeat_rule"):
                parts.append(f"循环规则：{updated['repeat_rule']}")
        return {
            "reply": "\n".join(parts),
            "history": _clear_session_state(history),
        }
    else:
        return {"reply": f"⚠️ 修改日程{sid}失败，请稍后重试。", "history": history}


# ============================================================
# 到期提醒检查（供 API 使用）
# ============================================================

def check_due_reminders() -> list[dict[str, str]]:
    """
    检查到期的日程提醒
    返回格式：[{"content": "...", "reminder_text": "..."}, ...]
    """
    due_schedules = get_due_schedules()
    if not due_schedules:
        return []

    reminders = []
    for s in due_schedules:
        reminder_text = _get_reminder_text(s["content"])
        reminders.append({
            "content": s["content"],
            "event_time": s["event_time"],
            "id": s["id"],
            "reminder_text": reminder_text,
        })
        # 如果是一次性日程，标记为已完成
        if not s.get("repeat_rule"):
            update_schedule(s["id"], status="completed")
        # 循环日程保留 active，让下次循环继续触发

    return reminders
