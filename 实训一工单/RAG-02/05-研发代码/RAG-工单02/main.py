from app.api.routes import router
from app.core.config import settings
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from debug.debug_router import debug_router


app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(router, prefix="/api/v1")
app.include_router(debug_router, prefix="/api/v1")

# Mount debug static files for the frontend
_debug_dir = os.path.join(os.path.dirname(__file__), "debug")
if os.path.isdir(_debug_dir):
    app.mount("/debug", StaticFiles(directory=_debug_dir, html=True), name="debug")


@app.get("/")
async def root() -> dict:
    return {
        "message": "RAG Prospectus QA API is running",
        "docs": "/docs",
    }
