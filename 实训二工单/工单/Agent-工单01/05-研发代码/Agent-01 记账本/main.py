"""记账本智能体 - FastAPI 服务入口
工单编号：人工智能NLP-Agent数字人项目-01-记账本任务工单V1.1-20250206
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import SERVER_HOST, SERVER_PORT
from agent import AccountBookAgent


app = FastAPI()

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = AccountBookAgent()

# 挂载静态文件
app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")


@app.get("/")
async def root():
    return RedirectResponse(url="/ui/index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_input = data.get("message", "")
    result = agent.process_message(user_input)
    return JSONResponse(content=result)


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
