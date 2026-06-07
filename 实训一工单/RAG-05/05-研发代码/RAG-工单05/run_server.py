"""启动uvicorn服务"""
import os, sys
os.chdir(r"C:\Users\刘禹含\Desktop\RAG-工单04")
sys.path.insert(0, r"C:\Users\刘禹含\Desktop\RAG-工单04")

import uvicorn
from main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
