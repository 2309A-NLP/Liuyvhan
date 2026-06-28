"""统一响应结构。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class APIResponse(BaseModel):
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    success: bool = True
    message: str = "ok"
    data: dict[str, Any] = Field(default_factory=dict)
    trace: list[str] = Field(default_factory=list)
    intent: str | None = None
    state: str | None = None
