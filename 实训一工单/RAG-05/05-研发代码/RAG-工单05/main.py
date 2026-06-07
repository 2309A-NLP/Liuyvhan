from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.debug_routes import debug_router
from app.api.routes import router
from app.core.config import settings


app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(router, prefix="/api/v1")
app.include_router(debug_router, prefix="/api/v1")

# 提供 stage_viewer.html
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root() -> dict:
    return {
        "message": "RAG Prospectus QA API is running",
        "docs": "/docs",
    }
