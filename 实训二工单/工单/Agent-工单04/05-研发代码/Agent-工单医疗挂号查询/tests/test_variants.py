from __future__ import annotations

import pytest

from tests.conftest import client


def test_chinese_date_expr_parse() -> None:
    from app.agent.intent_service import IntentService

    parsed = IntentService().parse("取消掉2026年6月28日我挂的上午十点牙科号")

    assert parsed.intent == "cancel_appointment"
    assert parsed.slots["date_expr"] == "2026-06-28"
    assert parsed.slots["time_expr"] == "上午10点"
    assert "date_expr" not in parsed.missing_slots


@pytest.mark.parametrize(
    ("query", "user_id", "status_code", "expected_state", "message_contains"),
    [
        ("我要挂号", 1, 200, "NEED_INFO", "信息不足"),
        ("帮我本人挂今天下午2点儿科专家号", 1, 200, "BOOKED", "预约"),
        ("帮我大宝挂今天下午2点儿科专家号", 999, 400, "FAILED", "未找到当前用户"),
        ("帮我三宝挂今天下午2点儿科专家号", 1, 400, "FAILED", "无权操作"),
        ("帮我大宝挂今天下午25点儿科专家号", 1, 400, "FAILED", "时间信息不够明确"),
        ("帮我大宝挂今天下午2点肿瘤科专家号", 1, 400, "FAILED", "未找到该科室"),
        ("帮我大宝挂今天下午2点王小明医生的号", 1, 400, "FAILED", "未找到该医生"),
        ("取消我昨天挂的神经内科普通号", 1, 200, "NEED_INFO", "信息不足"),
        ("牙科最近号源", 1, 200, "AVAILABLE", "最近可用号源"),
        ("帮我查下张建国医生下周排班", 1, 200, "AVAILABLE", "坐诊安排"),
        ("我之前挂过眼科专家，再约那个医生", 1, 200, "BOOKED", "重新预约"),
        ("我想取消挂号", 1, 200, "NEED_INFO", "信息不足"),
        ("帮我查皮肤科最近还有号吗", 1, 200, "AVAILABLE", "最近可用号源"),
        ("帮我本人挂明天上午9点皮肤科普通号", 1, 200, "BOOKED", "预约"),
        ("帮我本人再挂明天上午9点皮肤科普通号", 1, 200, "BOOKED", "预约"),
        ("取消我上周三挂的消化内科普通号", 1, 200, "CANCELLED", "取消"),
        ("取消我上周三挂的消化内科普通号", 3, 400, "FAILED", "未找到可取消"),
        ("帮我查下牙科医生坐诊", 1, 200, "AVAILABLE", "坐诊安排"),
        ("帮我查下皮肤科医生明天坐诊", 1, 200, "AVAILABLE", "坐诊安排"),
        ("帮我查下张建国医生今天坐诊", 1, 200, "AVAILABLE", "坐诊安排"),
        ("帮我本人挂下周上午9点儿科专家号", 1, 200, "BOOKED", "预约"),
        ("帮我本人挂下周上午9点儿科普通号", 1, 400, "FAILED", "无可用号源"),
        ("帮我查下消化内科最近号源", 1, 400, "FAILED", "无可用号源"),
        ("帮我本人挂最近眼科专家号", 1, 200, "BOOKED", "预约"),
        ("帮我查下眼科最近还有号吗", 1, 200, "AVAILABLE", "最近可用号源"),
        ("帮我本人挂明天上午9点皮肤科普通号", 3, 200, "BOOKED", "预约"),
        ("帮我查张建国医生下周坐诊", 1, 200, "AVAILABLE", "坐诊安排"),
        ("帮我查下儿科最近号源", 1, 200, "AVAILABLE", "最近可用号源"),
        ("帮我取消张建国医生的号", 1, 200, "NEED_INFO", "信息不足"),
        ("帮我查下王小明医生下周坐诊", 1, 400, "FAILED", "未找到该医生"),
        ("帮我二宝挂明天上午9点皮肤科普通号", 1, 200, "BOOKED", "预约"),
        ("帮我本人挂2026-99-99上午9点皮肤科普通号", 1, 400, "FAILED", "时间信息不够明确"),
        ("帮我本人挂后天上午8点牙科普通号", 1, 400, "FAILED", "无可用号源"),
        ("帮我查牙科最近的号哪天的", 1, 200, "AVAILABLE", "最近可用号源"),
        ("帮我本人挂明天上午十点牙科号", 1, 200, "BOOKED", "预约"),
        ("帮我本人挂明天下午三点牙科号", 1, 400, "FAILED", "无可用号源"),
    ],
)
def test_variants(query: str, user_id: int, status_code: int, expected_state: str, message_contains: str) -> None:
    response = client.post(
        "/api/agent/chat",
        json={"user_id": user_id, "session_id": f"variant-{abs(hash((query, user_id)))}", "query": query},
    )
    payload = response.json()
    assert response.status_code == status_code
    assert payload["state"] == expected_state
    assert message_contains in payload["message"]


def test_time_conflict_when_booking_same_slot_twice() -> None:
    first = client.post(
        "/api/agent/chat",
        json={"user_id": 1, "session_id": "conflict-1", "query": "帮我本人挂今天下午2点儿科专家号"},
    )
    second = client.post(
        "/api/agent/chat",
        json={"user_id": 1, "session_id": "conflict-2", "query": "帮我本人挂今天下午2点儿科专家号"},
    )
    assert first.status_code == 200
    assert second.status_code == 400
    assert "已有预约" in second.json()["message"]
