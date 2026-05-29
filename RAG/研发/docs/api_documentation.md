# 接口文档

## 1. 接口概览

本项目后端基于 FastAPI，实现了页面访问、用户管理、角色查询、聊天、会话历史和知识库重载等接口。

当前常用访问地址：

- 首页：`http://127.0.0.1:8001/`
- 工作台：`http://127.0.0.1:8001/workspace`
- 健康检查：`http://127.0.0.1:8001/health`

说明：

- 端口由 `.env` 中的 `APP_PORT` 控制
- 当前项目主端口配置为 `8001`
- 如果端口被占用，应用可能自动顺延到后续可用端口，例如 `8002`

## 2. 通用说明

- 请求与响应格式：`application/json`
- 字符编码：`UTF-8`
- 流式接口：`/chat/stream`
- 普通接口错误时会返回标准 HTTP 状态码和错误信息

## 3. 页面访问接口

### 3.1 首页

- 方法：`GET`
- 路径：`/`
- 说明：返回首页页面 `frontend/index.html`

### 3.2 工作台

- 方法：`GET`
- 路径：`/workspace`
- 说明：返回工作台页面 `frontend/workspace.html`

### 3.3 图标

- 方法：`GET`
- 路径：`/favicon.ico`
- 说明：重定向到静态图标资源

## 4. 健康检查

### 4.1 查询服务状态

- 方法：`GET`
- 路径：`/health`
- 说明：查看服务状态、模型提供方、Embedding 后端和当前存储模式

响应示例：

```json
{
  "status": "ok",
  "llm_provider": "siliconflow",
  "embedding_backend": "hashing",
  "storage_mode": "milvus/redis"
}
```

字段说明：

- `status`：服务状态
- `llm_provider`：当前大模型提供方
- `embedding_backend`：当前向量化后端
- `storage_mode`：当前记忆存储模式，格式为 `长期记忆/短期记忆`

## 5. 用户接口

### 5.1 创建或更新用户

- 方法：`POST`
- 路径：`/users`

请求示例：

```json
{
  "user_id": "user-001",
  "name": "张三",
  "profile": {
    "city": "上海",
    "goal": "希望获得更稳定的建议"
  }
}
```

响应示例：

```json
{
  "user_id": "user-001",
  "name": "张三",
  "profile": {
    "city": "上海",
    "goal": "希望获得更稳定的建议"
  }
}
```

字段说明：

- `user_id`：用户唯一标识，可选，不传时系统自动生成
- `name`：用户名称
- `profile`：用户补充信息

## 6. 角色接口

### 6.1 获取角色列表

- 方法：`GET`
- 路径：`/roles`

响应字段说明：

- `role_id`：角色唯一标识
- `name`：角色名称
- `domain`：角色领域
- `description`：角色简介
- `personality`：角色性格
- `tone`：角色语气
- `system_rules`：角色规则约束
- `prompt_template`：角色提示词模板
- `metadata`：扩展元数据

## 7. 聊天接口

### 7.1 普通聊天

- 方法：`POST`
- 路径：`/chat`

请求示例：

```json
{
  "session_id": "session-001",
  "user_id": "user-001",
  "role_id": "psychologist",
  "message": "我最近压力很大，总是睡不好，应该怎么调整？"
}
```

响应示例：

```json
{
  "session_id": "session-001",
  "role_id": "psychologist",
  "answer": "你现在更需要先稳定节奏，而不是一下子解决所有问题。可以先从睡前一小时减少刺激、固定入睡时间、记录压力来源开始。",
  "references": [
    {
      "doc_id": "psy-001-chunk-1",
      "title": "基础心理支持流程",
      "content": "心理支持型对话建议采用共情、澄清、聚焦、行动四步法。",
      "source": "synthetic/psychology_support_notes",
      "score": 0.82
    }
  ],
  "memory_size": 2
}
```

字段说明：

- `session_id`：会话 ID
- `user_id`：用户 ID
- `role_id`：角色 ID
- `message`：当前用户输入
- `answer`：模型生成的回答
- `references`：知识检索引用片段
- `memory_size`：当前短期记忆条数

### 7.2 流式聊天

- 方法：`POST`
- 路径：`/chat/stream`
- 返回类型：`application/x-ndjson`

请求示例：

```json
{
  "session_id": "session-001",
  "user_id": "user-001",
  "role_id": "legal_consultant",
  "message": "如果对方拖欠款项，我应该先怎么保留证据？"
}
```

流式事件说明：

- `type=chunk`：流式文本片段
- `type=done`：回答完成
- `type=error`：本轮生成出错

`chunk` 示例：

```json
{
  "type": "chunk",
  "content": "建议你先整理"
}
```

`done` 示例：

```json
{
  "type": "done",
  "answer": "建议你先整理合同、聊天记录、转账记录和催款记录，再考虑下一步正式通知。",
  "references": [
    {
      "doc_id": "law-001-chunk-2",
      "title": "民事证据整理建议",
      "content": "发生欠款争议时，应优先固定合同、付款、沟通和催告记录。",
      "source": "synthetic/legal_notes",
      "score": 0.79
    }
  ],
  "memory_size": 4,
  "session_id": "session-001",
  "role_id": "legal_consultant"
}
```

`error` 示例：

```json
{
  "type": "error",
  "detail": "Upstream LLM request failed."
}
```

## 8. 会话历史接口

### 8.1 查询会话历史

- 方法：`GET`
- 路径：`/sessions/{session_id}/history`

响应示例：

```json
{
  "session_id": "session-001",
  "messages": [
    {
      "role": "user",
      "content": "我最近压力很大。",
      "timestamp": "2026-04-29T11:30:00"
    },
    {
      "role": "assistant",
      "content": "先不用急着解决全部问题，可以先把压力来源拆开。",
      "timestamp": "2026-04-29T11:30:02"
    }
  ]
}
```

## 9. 知识库接口

### 9.1 重载演示知识库

- 方法：`POST`
- 路径：`/knowledge/reload`
- 说明：重新加载角色种子数据与知识种子数据

响应示例：

```json
{
  "status": "ok",
  "message": "Demo data reloaded.",
  "roles": 4,
  "knowledge_chunks": 12
}
```

## 10. 状态码说明

- `200`：请求成功
- `404`：资源不存在，例如角色不存在
- `422`：请求参数校验失败
- `500`：服务内部错误

## 11. 当前接口特点

- 支持普通聊天和流式聊天两种模式
- 支持通过 `session_id` 隔离不同会话上下文
- 支持通过 `role_id` 实现角色知识库隔离检索
- 支持 Redis 与 Milvus 的真实后端接入
- 支持健康接口快速判断当前是否运行在 `milvus/redis` 模式
- 当前推荐通过 `start-stack.ps1` 或 `start-stack.cmd` 启动整套服务
