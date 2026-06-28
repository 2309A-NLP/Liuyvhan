"""通用状态管理。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.registration.models import AgentTaskState


class StateService:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_state(
        self,
        *,
        user_id: int,
        session_id: str,
        query: str,
        intent: str,
        slots_json: str,
        state: str,
        result: str = "",
    ) -> AgentTaskState:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        task_state = self.db.scalar(
            select(AgentTaskState).where(
                AgentTaskState.user_id == user_id,
                AgentTaskState.session_id == session_id,
            )
        )
        now = datetime.now()
        if not task_state:
            task_state = AgentTaskState(
                user_id=user_id,
                session_id=session_id,
                query=query,
                intent=intent,
                slots_json=slots_json,
                state=state,
                result=result,
                created_at=now,
                updated_at=now,
            )
            self.db.add(task_state)
        else:
            task_state.query = query
            task_state.intent = intent
            task_state.slots_json = slots_json
            task_state.state = state
            task_state.result = result
            task_state.updated_at = now
        self.db.flush()
        return task_state
