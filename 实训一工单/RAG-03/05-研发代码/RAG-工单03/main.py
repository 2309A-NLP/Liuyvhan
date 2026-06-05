from app.api.routes import router
from app.core.config import settings
from fastapi import FastAPI


app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    return {
        "message": "RAG Prospectus QA API is running",
        "docs": "/docs",
    }
