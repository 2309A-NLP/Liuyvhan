"""FastAPI 启动入口。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.common.error_handler import register_exception_handlers
from app.config import settings
from app.registration.router import router as registration_router

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "index.html"


def create_app() -> FastAPI:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    app = FastAPI(title=settings.project_name)
    register_exception_handlers(app)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.include_router(registration_router, prefix="/api")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

        _ = request
        if TEMPLATE_PATH.exists():
            return HTMLResponse(content=TEMPLATE_PATH.read_text(encoding="utf-8"))
        return HTMLResponse(
            content=f"<h1>{settings.project_name}</h1><p>前端模板未找到。</p>",
            status_code=500,
        )

    return app


app = create_app()
