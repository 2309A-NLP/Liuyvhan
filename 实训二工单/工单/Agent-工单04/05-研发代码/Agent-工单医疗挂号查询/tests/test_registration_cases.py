from __future__ import annotations


def test_case_1_book_pediatrics_expert() -> None:
    from tests.conftest import client

    response = client.post(
        "/api/agent/chat",
        json={"user_id": 1, "session_id": "case-1", "query": "帮我大宝挂一个今天下午 2 点儿科专家的号"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["state"] == "BOOKED"
    assert "大宝" in payload["message"]


def test_case_2_query_nearest_dentistry_slots() -> None:
    from tests.conftest import client

    response = client.post(
        "/api/agent/chat",
        json={"user_id": 1, "session_id": "case-2", "query": "牙科最近的号哪天的？"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["state"] == "AVAILABLE"
    assert payload["data"]["schedules"][0]["department_name"] == "牙科"


def test_case_3_repeat_previous_eye_expert() -> None:
    from tests.conftest import client

    response = client.post(
        "/api/agent/chat",
        json={"user_id": 1, "session_id": "case-3", "query": "我之前挂过眼科的一个专家，帮我再约那个专家的号"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["state"] == "BOOKED"
    assert payload["data"]["doctor_name"] == "眼科专家医生"


def test_case_4_query_skin_slots_for_tomorrow_morning() -> None:
    from tests.conftest import client

    response = client.post(
        "/api/agent/chat",
        json={"user_id": 1, "session_id": "case-4", "query": "我明天上午 9 点想带二宝看皮肤科，还有号吗？"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["state"] == "AVAILABLE"
    assert payload["data"]["schedules"][0]["department_name"] == "皮肤科"


def test_case_5_cancel_last_wednesday_digestive() -> None:
    from tests.conftest import client

    response = client.post(
        "/api/agent/chat",
        json={"user_id": 1, "session_id": "case-5", "query": "取消我上周三挂的消化内科普通号"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["state"] == "CANCELLED"


def test_case_6_query_zhang_jianguo_next_week_schedule() -> None:
    from tests.conftest import client

    response = client.post(
        "/api/agent/chat",
        json={"user_id": 1, "session_id": "case-6", "query": "帮我查下张建国医生下周的坐诊时间"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["state"] == "AVAILABLE"
    assert len(payload["data"]["schedules"]) >= 1
