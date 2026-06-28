"""
日程管家 - FastAPI 服务入口
工单：人工智能 NLP-Agent 数字人项目-日程管家任务

启动命令：
    python main.py
    或
    uvicorn main:app --host 0.0.0.0 --port 8012 --reload
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import check_due_reminders, process_schedule_message
from config import SETTINGS
from database import init_database, query_schedules as db_query_schedules

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

class ChatRequest(BaseModel):
    """日程聊天请求"""
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """日程聊天响应"""
    reply: str
    history: list[dict[str, str]] | None = None


# ============================================================
# 应用初始化
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("正在初始化数据库...")
    try:
        init_database()
        logger.info("✅ 数据库初始化成功")
    except Exception as e:
        logger.error("数据库初始化失败: %s", e)
    yield
    logger.info("服务关闭")


app = FastAPI(
    title=SETTINGS.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置 - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API 路由
# ============================================================

@app.get("/health")
async def health():
    """健康检查 - 返回服务状态"""
    return {
        "service": SETTINGS.app_name,
        "version": "1.0.0",
        "status": "running",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """处理用户日程消息"""
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    try:
        result = process_schedule_message(request.message, request.history)
        return ChatResponse(
            reply=result["reply"],
            history=result.get("history"),
        )
    except Exception as e:
        logger.exception("处理日程消息失败")
        return ChatResponse(reply=f"❌ 处理失败: {str(e)}")


@app.get("/list")
async def list_schedules(
    date: str | None = None,
    status: str | None = None,
):
    """
    获取日程列表
    支持 date 参数：today / tomorrow / this_week / YYYY-MM-DD
    """
    from datetime import datetime, timedelta

    filters: dict[str, Any] = {}
    now = datetime.now()

    if date == "today" or not date:
        today = now.strftime("%Y-%m-%d")
        filters["date_from"] = f"{today} 00:00:00"
        filters["date_to"] = f"{today} 23:59:59"
    elif date == "tomorrow":
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        filters["date_from"] = f"{tomorrow} 00:00:00"
        filters["date_to"] = f"{tomorrow} 23:59:59"
    elif date == "this_week":
        monday = now - timedelta(days=now.weekday())
        sunday = monday + timedelta(days=6)
        filters["date_from"] = f"{monday.strftime('%Y-%m-%d')} 00:00:00"
        filters["date_to"] = f"{sunday.strftime('%Y-%m-%d')} 23:59:59"
    else:
        # YYYY-MM-DD 格式
        filters["date_from"] = f"{date} 00:00:00"
        filters["date_to"] = f"{date} 23:59:59"

    if status:
        filters["status"] = status

    schedules = db_query_schedules(filters)
    return {"total": len(schedules), "schedules": schedules}


@app.get("/due")
async def check_due():
    """检查到期的日程提醒"""
    try:
        reminders = check_due_reminders()
        return {"reminders": reminders, "has_reminders": len(reminders) > 0}
    except Exception as e:
        logger.exception("检查到期提醒失败")
        return {"reminders": [], "has_reminders": False, "error": str(e)}


@app.get("/all")
async def list_all_schedules(status: str | None = None):
    """获取所有日程（用于前端列表展示）"""
    filters: dict[str, Any] = {}
    if status:
        filters["status"] = status
    schedules = db_query_schedules(filters)
    return {"total": len(schedules), "schedules": schedules}


# ============================================================
# 前端静态文件
# ============================================================

import os
from pathlib import Path

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
    local_url = f"http://localhost:{SETTINGS.port}"
    print(f"[日程管家] 服务启动中...")
    print(f"  地址: {local_url}")
    print(f"  接口: POST /chat")
    print(f"  日程: GET /list")
    print(f"  提醒: GET /due")
    print(f"  界面: {local_url}")
    uvicorn.run(
        "main:app",
        host=SETTINGS.host,
        port=SETTINGS.port,
        reload=False,
    )
