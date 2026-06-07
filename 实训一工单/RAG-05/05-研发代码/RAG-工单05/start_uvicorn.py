"""启动uvicorn服务器 - 从项目根目录"""
import sys, os

# 切换到项目目录
project_dir = r"C:\Users\刘禹含\Desktop\RAG-工单04"
os.chdir(project_dir)
sys.path.insert(0, project_dir)

# 导入app
from app.core.config import settings
from app.api.routes import router
from fastapi import FastAPI

app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "RAG Prospectus QA API is running", "docs": "/docs"}

import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
