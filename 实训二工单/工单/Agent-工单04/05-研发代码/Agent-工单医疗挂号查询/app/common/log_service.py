"""Agent 执行日志。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.registration.models import AgentLog


class LogService:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def log_step(
        self,
        *,
        user_id: int,
        session_id: str,
        query: str,
        intent: str,
        step_name: str,
        tool_name: str,
        tool_input: dict[str, Any] | None,
        tool_output: dict[str, Any] | None,
        status: str,
        error_message: str = "",
    ) -> AgentLog:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        record = AgentLog(
            user_id=user_id,
            session_id=session_id,
            query=query,
            intent=intent,
            step_name=step_name,
            tool_name=tool_name,
            tool_input=json.dumps(tool_input or {}, ensure_ascii=False, default=self._json_default),
            tool_output=json.dumps(tool_output or {}, ensure_ascii=False, default=self._json_default),
            status=status,
            error_message=error_message,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def get_logs(self, session_id: str) -> list[AgentLog]:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        return list(
            self.db.scalars(
                select(AgentLog).where(AgentLog.session_id == session_id).order_by(AgentLog.id.asc())
            )
        )

    @staticmethod
    def _json_default(value: Any) -> Any:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
