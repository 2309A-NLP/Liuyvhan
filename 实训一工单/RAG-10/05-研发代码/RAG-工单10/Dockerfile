# =============================================================================
# Dockerfile - RAG 金融问答系统
# 工单编号：人工智能 NLP-RAG-金融问答系统部署
# =============================================================================
# 多阶段构建：第一阶段下载模型，第二阶段运行服务
# 基于 Python 3.11-slim，平衡镜像大小与兼容性

# ----------------------------------------
# Stage 1: 模型下载阶段
# ----------------------------------------
FROM python:3.11-slim AS model-downloader

WORKDIR /models

# 安装基础工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安装 sentence-transformers（用于下载 embedding 模型）
RUN pip install --no-cache-dir sentence-transformers==3.4.1

# 下载 embedding 模型（预缓存到镜像中，避免运行时从 HuggingFace 下载）
RUN python3 -c "
from sentence_transformers import SentenceTransformer
print('[MODEL] 下载 embedding 模型...')
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
print('[MODEL] embedding 模型下载完成')
"

# 下载 CLIP 模型（用于图像语义解析）
RUN pip install --no-cache-dir transformers==4.44.0 pillow
RUN python3 -c "
from transformers import CLIPProcessor, CLIPModel
print('[MODEL] 下载 CLIP 模型...')
CLIPModel.from_pretrained('openai/clip-vit-base-patch32')
CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32')
print('[MODEL] CLIP 模型下载完成')
"

# ----------------------------------------
# Stage 2: 运行阶段
# ----------------------------------------
FROM python:3.11-slim AS runtime

LABEL maintainer="RAG Team"
LABEL description="RAG 金融问答系统 - Docker 容器化部署"
LABEL ticket="人工智能 NLP-RAG-金融问答系统部署"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
# - poppler-utils: pdfplumber/pymupdf 解析 PDF 需要
# - gcc, g++: torch 安装编译需要
# - libgomp1: torch 并行计算需要
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    gcc \
    g++ \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从模型下载阶段复制缓存的模型
COPY --from=model-downloader /root/.cache/huggingface /root/.cache/huggingface

# 设置环境变量：使用本地缓存的模型（离线模式）
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 复制项目依赖文件并安装 Python 包
COPY requirements.txt .

# 安装 Python 依赖
# torch 在 slim 镜像中需要额外指定索引
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建数据目录结构（挂载点）
RUN mkdir -p /app/data/raw /app/data/processed /app/data/processed/images /app/data/exports /app/static

# 创建非 root 用户运行（安全性）
RUN groupadd -r rag && useradd -r -g rag -d /app -s /sbin/nologin rag
RUN chown -R rag:rag /app

# 暴露 API 端口
EXPOSE 8000

# 切换到非 root 用户
USER rag

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/api/v1/health || exit 1

# 启动命令
# 使用 run_uvicorn.py 启动，它从 .env 读取配置
CMD ["python", "run_uvicorn.py"]
