
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    user_id: str | None = None
    name: str
    profile: dict[str, Any] = Field(default_factory=dict)


class User(BaseModel):
    user_id: str
    name: str
    profile: dict[str, Any] = Field(default_factory=dict)


class RoleProfile(BaseModel):
    role_id: str  # 角色唯一编号
    name: str
    domain: str   # 角色领域
    description: str  #角色描述
    personality: str  # 角色性格
    tone: str         # 角色语气
    system_rules: list[str] # 角色规则列表
    prompt_template: str    # 提示词模板
    metadata: dict[str, Any] = Field(default_factory=dict) # 额外补充信息


class KnowledgeDocument(BaseModel):
    doc_id: str
    role_id: str
    title: str
    content: str
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)

"""
ChatRequest --- 是一种数据模式 专门规定聊天请求数据格式
"""
class ChatRequest(BaseModel):
    session_id: str
    user_id: str
    role_id: str
    message: str


class RetrievedChunk(BaseModel):
    doc_id: str
    title: str
    content: str
    source: str
    score: float


class ChatResponse(BaseModel):
    session_id: str
    role_id: str
    answer: str
    references: list[RetrievedChunk]
    memory_size: int


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    embedding_backend: str
    storage_mode: str


class KnowledgeReloadResponse(BaseModel):
    status: str
    message: str
    roles: int
    knowledge_chunks: int


class PDFImportStatusItem(BaseModel):
    pdf_path: str
    status: str
    fingerprint: str | None = None
    role_id: str | None = None
    chunks: int | None = None
    error: str | None = None


class PDFImportStatusResponse(BaseModel):
    summary: dict[str, int]
    items: list[PDFImportStatusItem]
