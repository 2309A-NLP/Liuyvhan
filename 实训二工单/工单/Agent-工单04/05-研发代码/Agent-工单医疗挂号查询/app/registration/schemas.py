"""挂号相关请求和响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    user_id: int
    session_id: str
    query: str


class AppointmentItem(BaseModel):
    id: int
    patient_name: str
    doctor_name: str
    department_name: str
    appointment_time: str
    slot_type: str
    status: str


class ScheduleItem(BaseModel):
    id: int
    doctor_name: str
    department_name: str
    work_date: str
    start_time: str
    end_time: str
    slot_type: str
    remain_count: int
    status: str


class InitDBResult(BaseModel):
    success: bool = True
    message: str = "数据库初始化完成"
    data: dict[str, Any] = Field(default_factory=dict)
    trace: list[str] = Field(default_factory=list)
