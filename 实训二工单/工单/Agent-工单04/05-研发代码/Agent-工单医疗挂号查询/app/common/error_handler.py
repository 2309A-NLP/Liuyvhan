"""错误恢复与异常处理。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.common.response_schema import APIResponse

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    def __init__(
        self,
        message: str,
        *,
        code: str = "AGENT_ERROR",
        status_code: int = 400,
        data: dict[str, Any] | None = None,
        trace: list[str] | None = None,
        intent: str | None = None,
        state: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data or {}
        self.trace = trace or []
        self.intent = intent
        self.state = state


class UserNotFoundError(AgentError):
    pass


class InvalidTimeExpressionError(AgentError):
    pass


class DepartmentNotFoundError(AgentError):
    pass


class DoctorNotFoundError(AgentError):
    pass


class SlotUnavailableError(AgentError):
    pass


class TimeConflictError(AgentError):
    pass


class PermissionDeniedError(AgentError):
    pass


class DatabaseOperationError(AgentError):
    pass


def build_error_response(error: AgentError) -> APIResponse:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    return APIResponse(
        success=False,
        message=error.message,
        data={"error_code": error.code, **error.data},
        trace=error.trace,
        intent=error.intent,
        state=error.state,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    @app.exception_handler(AgentError)
    async def handle_agent_error(_: Request, exc: AgentError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=build_error_response(exc).model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected error: %s", exc)
        response = APIResponse(
            success=False,
            message="系统繁忙，请稍后重试。",
            data={"error_code": "INTERNAL_SERVER_ERROR"},
            trace=["系统发生未预期异常，已记录日志。"],
        )
        return JSONResponse(status_code=500, content=response.model_dump())
