# 代码阅读导图

## 1. 这份导图是干什么的

这份文档不是接口文档，也不是设计文档。

它的目标只有一个：

- 帮你按“实际执行链路”看懂这套 RAG 大模型项目

你学习这套代码时，最容易混乱的点通常不是某一行语法，而是：

- 请求是从哪里进来的
- 角色设定、记忆、知识检索在哪里拼起来
- 大模型到底是在哪个文件里被真正调用的
- Redis 和 Milvus 分别负责什么

所以这份导图按“用户发一句话之后，系统内部发生了什么”来讲。

---

## 2. 先记住这条主链路

用户在前端发送一句话后，后端主链路是：

```text
main.py
  -> ChatService
      -> MemoryManager（读短期记忆 / 查长期记忆）
      -> Retriever（查知识库）
      -> build_system_prompt（拼系统提示词）
      -> LLMClient（调用上游大模型）
      -> MemoryManager（写回短期记忆 / 长期记忆）
  -> 返回前端
```

如果你先把这条链路记住，后面每个文件就不容易看乱。

---

## 3. 推荐阅读顺序

建议按下面顺序看：

1. `main.py`
2. `models/schemas.py`
3. `modules/chat.py`
4. `modules/role_prompts.py`
5. `core/llm_client.py`
6. `modules/memory.py`
7. `core/retriever.py`
8. `core/embedding.py`
9. `database/redis_client.py`
10. `database/milvus_client.py`
11. `config.py`

这样看最符合真实执行顺序。

---

## 4. 每个核心文件看什么

### 4.1 `main.py`

这是后端总入口。

你重点看 3 件事：

- `build_services()`
- `create_app()`
- `/chat` 和 `/chat/stream`

它的作用是：

- 创建所有服务对象
- 把服务挂到 `FastAPI`
- 暴露接口给前端调用

你可以把它理解成：

- “总装配厂”

这里本身不做复杂业务判断，它主要负责把各个模块接起来。

---

### 4.2 `models/schemas.py`

这是数据模型定义文件。

你重点看：

- `ChatRequest`
- `ChatResponse`
- `RetrievedChunk`
- `RoleProfile`

它的作用是：

- 规定接口收什么数据
- 规定接口返回什么数据
- 规定检索结果长什么样

如果你不先看这些模型，后面看到参数时会不知道每个字段代表什么。

---

### 4.3 `modules/chat.py`

这是对话主编排器，是整个系统最关键的业务文件之一。

重点函数：

- `chat()`
- `stream_chat()`
- `_build_context()`
- `_finalize_response()`

它负责：

- 查角色
- 读短期记忆
- 查长期记忆
- 查知识库
- 组装系统提示词
- 调用大模型
- 把答案写回记忆

你可以把它理解成：

- “一次聊天请求的总指挥”

如果只允许你先精读一个业务文件，那就先精读这个。

---

### 4.4 `modules/role_prompts.py`

这个文件专门负责生成 `system prompt`。

重点函数：

- `build_system_prompt()`
- `_format_short_memory()`
- `_format_long_memory()`
- `_format_knowledge()`

它负责把下面这些内容打包给大模型：

- 角色设定
- 用户当前问题
- 短期记忆
- 长期记忆
- 检索出的知识片段
- 输出规则

这一步非常关键，因为：

- 大模型最后看到的“上下文”，主要就是这里拼出来的

换句话说：

- 这里决定了模型“知道什么背景”
- `llm_client.py` 决定了模型“怎么被调用”

---

### 4.5 `core/llm_client.py`

这个文件是真正调用大模型的地方。

重点函数：

- `generate()`
- `generate_stream()`
- `_generate_openai_compatible()`
- `_collect_openai_compatible_stream()`
- `_build_openai_payload()`
- `_finalize_answer()`

你要重点理解：

- 上游模型接口在哪里调用
- 请求体是怎么组装的
- 返回结果是怎么清洗的

当前项目里，大模型调用不是直接写很多复杂逻辑，而是比较清楚地分成三步：

1. 组请求
2. 发请求
3. 清洗结果

这里是你学习“大模型接 API”的最核心文件。

---

### 4.6 `modules/memory.py`

这个文件是记忆层编排器。

重点函数：

- `get_short_memory()`
- `append_turn()`
- `maybe_write_long_term()`
- `search_long_memory()`

它负责两类记忆：

- 短期记忆：当前会话最近几轮聊天
- 长期记忆：用户偏好、身份、目标等更长期的信息

你要重点区分：

- 短期记忆按 `session_id` 查
- 长期记忆按 `user_id` 查

这是理解“为什么同一个用户不同会话还能保留一部分信息”的关键。

---

### 4.7 `core/retriever.py`

这是知识检索器。

重点函数：

- `retrieve()`
- `_search_candidates()`
- `_filter_candidates()`
- `_build_query_variants()`

它做的事情可以概括成：

1. 把用户问题改写成多个查询版本
2. 去 Milvus 召回候选知识
3. 做重排和去重
4. 返回最适合引用的知识片段

这部分属于标准 RAG 的 “R”。

---

### 4.8 `core/embedding.py`

这是向量化模块。

重点函数：

- `embed_texts()`
- `embed_text()`

它负责：

- 把文本变成向量

当前不是重型真实模型，而是：

- `HashingVectorizer`

所以它更像：

- “为了先跑通 RAG 链路的轻量 Embedding 替身”

你要明白一点：

- 现在项目的向量检索结构是真实的
- 但向量本身的生成方式还是轻量实现

---

### 4.9 `database/redis_client.py`

这是短期记忆存储网关。

重点看：

- `RedisClient`
- `_RemoteRedisBackend`
- `_LocalRedisBackend`

它的设计思想是：

- 上层只管“存 / 取消息”
- 不关心底层到底是 Redis 还是本地 JSON 文件

这叫：

- 统一接口 + 可降级后端

---

### 4.10 `database/milvus_client.py`

这是向量库存储网关。

重点看：

- `MilvusClient`
- `_RemoteMilvusBackend`
- `_LocalMilvusBackend`
- `search()`
- `upsert_documents()`

它负责两类向量数据：

- 角色知识库
- 用户长期记忆

你可以理解成：

- Milvus 在这个项目里，不只是知识库，还承担长期记忆向量检索

---

### 4.11 `config.py`

这是全局配置中心。

重点看：

- `Settings`
- `_load_dotenv()`

它负责：

- 从 `.env` 读取配置
- 统一给全项目使用

你后面如果想改：

- 模型名
- 端口
- Redis / Milvus 地址
- 检索参数

基本都要从这里顺藤摸瓜。

---

## 5. 一次聊天请求的内部流程

下面用最接近真实运行的方式讲一遍。

### 第 1 步：前端发请求

前端把一条消息发给：

- `POST /chat`
或
- `POST /chat/stream`

请求体对应：

- `models/schemas.py` 里的 `ChatRequest`

核心字段是：

- `session_id`
- `user_id`
- `role_id`
- `message`

---

### 第 2 步：`main.py` 接住请求

`main.py` 里的接口函数拿到请求后，不直接处理业务，而是交给：

- `ChatService`

这里体现了一个很重要的设计思想：

- 接口层只负责转发
- 业务层负责真正处理

---

### 第 3 步：`ChatService` 组装上下文

在 `modules/chat.py` 的 `_build_context()` 里，会做几件事：

1. 查角色信息
2. 读取短期记忆
3. 查询长期记忆
4. 查询知识库
5. 生成 `system_prompt`

这一步的结果就是：

- 给大模型准备好完整输入背景

---

### 第 4 步：查短期记忆

`MemoryManager.get_short_memory()` 会按 `session_id` 去 Redis 取消息。

也就是说：

- 当前会话最近聊了什么，存在 Redis 里

它取回来之后还会顺手清洗一遍内容，避免乱码继续污染上下文。

---

### 第 5 步：查长期记忆

`MemoryManager.search_long_memory()` 会：

1. 先把当前问题向量化
2. 再去 Milvus 的长期记忆集合里搜索
3. 按 `user_id` 过滤

所以长期记忆本质上是：

- “某个用户过去留下的可长期复用信息”

---

### 第 6 步：知识检索

`Retriever.retrieve()` 会：

1. 构造多个查询版本
2. 逐个向量化
3. 到 Milvus 的知识库集合里搜索
4. 用重排器重新排序
5. 截取最有价值的片段

这里的检索目标是：

- 跟当前角色相关的知识库

所以会带：

- `role_id` 过滤

---

### 第 7 步：拼 `system prompt`

`build_system_prompt()` 会把：

- 角色设定
- 用户当前问题
- 短期记忆
- 长期记忆
- 知识片段

拼成一个大字符串，作为系统提示词传给 LLM。

这也是这套项目最值得你学习的地方之一：

- RAG 并不是“模型自己知道记忆和知识”
- 而是程序先把背景整理好，再喂给模型

---

### 第 8 步：调用大模型

`core/llm_client.py` 里的 `generate()` 或 `generate_stream()` 会真正发请求。

当前调用方式是：

- OpenAI Compatible API

也就是你虽然现在接的是别家的模型服务，但只要它兼容 OpenAI 风格接口，就能接进来。

真正的核心请求体在：

- `_build_openai_payload()`

最关键的字段是：

- `model`
- `messages`
- `temperature`
- `max_tokens`

---

### 第 9 步：清洗模型输出

模型返回之后，还不会直接发给前端。

`_finalize_answer()` 会继续做：

- 清洗 `<br>`
- 清洗 `response`
- 清洗 `assistant`
- 判断是否乱码
- 必要时降级为本地 mock 回答

这一步很重要，因为真实 API 返回的文本不一定总是干净。

---

### 第 10 步：写回记忆

`ChatService._finalize_response()` 会：

1. 把本轮用户消息和助手回答写入短期记忆
2. 判断用户消息是否值得写入长期记忆

长期记忆当前只抓这类信息：

- 我喜欢……
- 我是……
- 我的目标……
- 我希望……
- 我不想……

这属于：

- 规则触发式长期记忆抽取

---

## 6. 你要特别理解的 5 个核心概念

### 6.1 `session_id`

代表一次会话。

作用：

- 隔离不同聊天窗口的短期上下文

---

### 6.2 `user_id`

代表一个用户。

作用：

- 让长期记忆能跨会话复用

---

### 6.3 `role_id`

代表当前扮演的角色。

作用：

- 决定角色人设
- 决定知识库过滤范围

---

### 6.4 `system_prompt`

这是喂给大模型的“完整背景说明书”。

它不是前端传来的，而是后端动态拼出来的。

---

### 6.5 `references`

这是知识检索返回的引用片段。

作用：

- 给模型补知识
- 给前端展示引用来源

---

## 7. 现在这套代码里，真正的“大模型部分”在哪里

如果你专门想学“大模型调用代码”，就重点盯住下面 3 个地方：

### 第一层：提示词工程

- `modules/role_prompts.py`

你要学的是：

- 后端如何组织模型上下文

### 第二层：模型请求封装

- `core/llm_client.py`

你要学的是：

- 如何组装 API 请求
- 如何支持普通回答和流式回答
- 如何清洗返回结果

### 第三层：RAG 上下文来源

- `modules/chat.py`
- `modules/memory.py`
- `core/retriever.py`

你要学的是：

- 模型的上下文不是凭空来的
- 而是由记忆和检索一起提供

---

## 8. 你可以这样开始精读

最推荐的精读方法是：

1. 先打开 `main.py`，找到 `/chat`
2. 顺着进入 `ChatService.chat()`
3. 再进入 `_build_context()`
4. 接着看 `build_system_prompt()`
5. 再看 `LLMClient.generate()`
6. 最后回来看 `MemoryManager` 和 `Retriever`

这样你是按真实执行顺序在学，不容易碎掉。

---

## 9. 你第一轮学习时，不要急着纠结的点

第一轮先不要过度纠结：

- 每个正则细节
- 每个日志字段
- 每个清洗函数的小分支
- 每个降级模式的小实现

第一轮最重要的是先看懂：

- 谁调用谁
- 数据从哪里来
- 数据到哪里去
- 大模型在哪一步被真正调用

---

## 10. 你学完这一轮后，下一轮该学什么

当你把主链路看顺以后，第二轮建议学：

1. `core/rerank.py`
2. `modules/knowledge.py`
3. `database/mysql_client.py`
4. `frontend/static/workspace.js`

第二轮重点是：

- 知识库初始化怎么做
- 角色数据怎么存
- 前端如何把流式回答渲染出来

---

## 11. 最后一句话总结

这套项目可以用一句话概括：

- 后端先把“角色 + 记忆 + 知识”整理成提示词，再调用上游大模型生成回答，最后把结果写回记忆系统。

只要你把这句话和第 2 节那条主链路记住，后面看代码会轻松很多。

---

## 12. 每个 Python 文件是干什么的

这一节只讲你自己项目里的 Python 文件，不讲 `.venv` 里的第三方库。

### 12.1 入口层

- `main.py`
  整个项目的总入口。负责创建服务、定义接口、启动网页和聊天 API。
- `config.py`
  配置中心。负责读取 `.env`，告诉项目端口、模型、Redis、Milvus 等参数。

### 12.2 `database` 目录

- `database/mysql_client.py`
  管理用户和角色基础信息。名字叫 MySQL，但你现在实际主要用的是这一层的本地数据库逻辑。
- `database/redis_client.py`
  管理短期对话记忆。最近几轮聊天存在这里。
- `database/milvus_client.py`
  管理向量库。知识库和长期记忆都通过它写入 Milvus、再从 Milvus 查出来。
- `database/__init__.py`
  包标记文件，本身业务作用很小。

### 12.3 `core` 目录

- `core/embedding.py`
  负责把文字变成向量。做知识检索和长期记忆检索前，都要先经过它。
- `core/rerank.py`
  负责重排序。把检索出来的候选结果再排一遍，让更相关的内容排前面。
- `core/retriever.py`
  检索器。负责去知识库里找和当前问题相关的资料。
- `core/llm_client.py`
  真正调用大模型接口的地方。也负责流式输出和回答清洗。
- `core/__init__.py`
  包标记文件。

### 12.4 `modules` 目录

- `modules/chat.py`
  对话总调度器。把角色、记忆、检索、模型调用串成完整聊天流程。
- `modules/memory.py`
  记忆管理器。负责短期记忆读取、长期记忆写入和检索。
- `modules/knowledge.py`
  知识库管理器。负责初始化知识、切块、向量化、写入 Milvus。
- `modules/role_prompts.py`
  提示词组装器。把角色设定、记忆和知识拼成 `system prompt` 给大模型。
- `modules/__init__.py`
  包标记文件。

### 12.5 `models` 目录

- `models/schemas.py`
  数据模型定义。规定聊天请求、聊天响应、角色信息这些数据长什么样。
- `models/__init__.py`
  包标记文件。

### 12.6 `utils` 目录

- `utils/logger.py`
  日志工具。负责把运行信息写进日志，方便排查。
- `utils/text_splitter.py`
  文本切块工具。把长文拆成适合入库检索的小段。
- `utils/text_sanitizer.py`
  文本清洗工具。处理乱码、脏字符、异常片段。
- `utils/__init__.py`
  包标记文件。

### 12.7 `scripts` 目录

- `scripts/init_mysql.py`
  初始化基础数据库用的脚本。
- `scripts/init_milvus.py`
  初始化 Milvus 用的脚本。
- `scripts/load_demo_data.py`
  加载演示角色和演示知识数据。

### 12.8 `tests` 目录

- `tests/test_chat.py`
  测聊天主流程是不是正常。
- `tests/test_api.py`
  测接口是不是正常。

### 12.9 评测与压测

- `evaluation/ragas_eval.py`
  用来评估 RAG 效果的脚本。
- `stress_test/stress_test.py`
  压力测试脚本。看系统多人或多请求时扛不扛得住。

### 12.10 最简单的记忆法

你可以这样记这套项目：

- `main.py` 负责开门
- `chat.py` 负责指挥聊天流程
- `memory.py` 负责记忆
- `retriever.py` 负责找资料
- `role_prompts.py` 负责拼提示词
- `llm_client.py` 负责问大模型
- `redis_client.py` 和 `milvus_client.py` 负责存东西

---

## 13. 项目架构图

下面这张图按“你运行项目时，数据和代码怎么流动”来画，最适合拿来整体理解。

```mermaid
flowchart TD
    U[用户 / 浏览器] --> FE[前端页面<br/>index.html / workspace.html]
    FE -->|HTTP / JSON| API[main.py<br/>FastAPI 应用入口]

    subgraph APP[后端应用层]
        API --> APPSTATE[app.state.services<br/>服务对象仓库]
        API --> HEALTH[/health]
        API --> ROLES[/roles]
        API --> USERS[/users]
        API --> CHAT[/chat /chat/stream]
        API --> HISTORY[/sessions/{id}/history]
        API --> RELOAD[/knowledge/reload]
    end

    subgraph SERVICE[业务服务层]
        BUILD[build_services()]
        CHATSVC[ChatService<br/>聊天总指挥]
        KNOW[KnowledgeManager<br/>知识库管理员]
        MEM[MemoryManager<br/>记忆管理器]
        RET[Retriever<br/>检索器]
        LLM[LLMClient<br/>大模型调用器]
        PROMPT[role_prompts.py<br/>系统提示词组装]
    end

    subgraph CORE[核心能力层]
        EMB[EmbeddingService<br/>文本转向量]
        RERANK[RerankService<br/>重排序]
    end

    subgraph STORAGE[存储层]
        SQLITE[app.db<br/>用户 / 角色]
        REDIS[Redis<br/>短期记忆]
        MILVUS[Milvus<br/>知识库 / 长期记忆]
    end

    subgraph SEED[种子数据层]
        ROLESJSON[roles.json<br/>角色原始资料]
        KNOWJSON[knowledge_documents.json<br/>知识原始资料]
    end

    BUILD --> CHATSVC
    BUILD --> KNOW
    BUILD --> MEM
    BUILD --> RET
    BUILD --> LLM
    BUILD --> EMB
    BUILD --> RERANK

    KNOW --> ROLESJSON
    KNOW --> KNOWJSON
    KNOW --> SQLITE
    KNOW --> EMB
    KNOW --> MILVUS

    MEM --> REDIS
    MEM --> MILVUS
    RET --> EMB
    RET --> MILVUS
    RET --> RERANK
    CHATSVC --> PROMPT
    CHATSVC --> MEM
    CHATSVC --> RET
    CHATSVC --> LLM
    CHATSVC --> SQLITE

    HEALTH --> MEM
    ROLES --> SQLITE
    USERS --> SQLITE
    CHAT --> CHATSVC
    HISTORY --> MEM
    RELOAD --> KNOW

    FE <-->|加载静态资源| STATIC[frontend/static<br/>JS / CSS / 图标]
    API --> STATIC
```

### 13.1 你可以这样读这张图

- 浏览器先进入前端页面
- 前端通过 HTTP / JSON 调后端接口
- `main.py` 负责创建 FastAPI 应用和注册路由
- `build_services()` 负责把所有服务对象组装好
- `ChatService` 负责聊天主流程调度
- `KnowledgeManager` 负责把角色和知识种子数据装进系统
- `MemoryManager` 负责短期和长期记忆
- `Retriever` 负责去 Milvus 找相关知识
- `LLMClient` 负责真正调用大模型
- `app.db / Redis / Milvus` 分别负责不同类型的数据存储

### 13.2 一句版流程

```text
浏览器 -> 前端页面 -> FastAPI -> ChatService -> 记忆/检索/提示词 -> LLM -> 写回记忆 -> 返回前端
```

### 13.3 纯文本架构图

如果你的查看器不支持 Mermaid，就直接看下面这个版本：

```text
用户 / 浏览器
  -> 前端页面(index.html / workspace.html)
  -> main.py(FastAPI应用入口)
  -> app.state.services(服务仓库)
      -> ChatService(聊天总指挥)
          -> MemoryManager(短期/长期记忆)
              -> Redis(短期记忆)
              -> Milvus(长期记忆)
          -> Retriever(知识检索)
              -> EmbeddingService(文本转向量)
              -> Milvus(知识库)
              -> RerankService(重排序)
          -> role_prompts.py(拼系统提示词)
          -> LLMClient(调用大模型)
          -> MySQLClient(查角色/用户)
  -> 返回 ChatResponse / 流式 chunk

KnowledgeManager(知识库初始化)
  -> roles.json(角色种子数据)
  -> knowledge_documents.json(知识种子数据)
  -> app.db(角色表/用户表)
  -> Milvus(role_knowledge集合)
```

---

## 14. 现在项目需要重点处理的 4 块

如果你现在是从“项目能跑”走向“项目能排查、能维护、能继续开发”，最需要盯住的就是下面 4 块：

1. 问题排查
2. 日志
3. 数据文件
4. 结构框架

这 4 块其实不是分开的，而是一条连续链路：

```text
用户报问题
  -> 先看日志里卡在哪一步
  -> 再看那一步依赖了哪个数据文件/存储
  -> 最后回到对应模块和结构层定位代码
```

---

## 15. 问题排查应该怎么抓

建议你把问题分成 4 类，不要混着查。

### 15.1 启动类问题

常见表现：

- 服务起不来
- 端口被占用
- 页面打不开
- Redis / Milvus 没连上

优先看：

- `main.py`
- `config.py`
- `start-stack.ps1`
- `logs/app.log`

重点日志关键词：

- `Configured port`
- `connection_ready`
- `backend=remote`
- `backend=local-file`
- `collection_loaded`

你当前日志里已经能看到两类典型现象：

- 端口 `8001` 被占用时，会自动回退到 `8002` 或 `8003`
- Redis / Milvus 成功连接时，会打印 `connection_ready`

也就是说，如果项目“看起来没起来”，第一件事不是先改代码，而是先确认：

- 实际启动到了哪个端口
- 当前到底连的是远程 Redis / Milvus，还是本地降级文件

---

### 15.2 对话类问题

常见表现：

- 能发消息，但回答不对
- 不记得上下文
- 角色感弱
- 没有正确引用知识

优先顺序：

1. `modules/chat.py`
2. `modules/memory.py`
3. `core/retriever.py`
4. `modules/role_prompts.py`
5. `core/llm_client.py`

你排查时要问自己 5 个问题：

1. 角色信息有没有查到
2. 短期记忆有没有读出来
3. 长期记忆有没有命中
4. 知识检索有没有命中
5. 最终拼给 LLM 的上下文是否合理

如果这 5 个问题里有一个断掉，最终回答就会偏。

---

### 15.3 存储类问题

常见表现：

- 聊天历史丢失
- 长期记忆没写进去
- 知识库搜不到
- 重启后数据不一致

对应关系要先记住：

- 短期记忆：Redis
- 长期记忆：Milvus
- 用户/角色基础数据：SQLite
- 降级存储：`data/storage/*.json`

优先看：

- `database/redis_client.py`
- `database/milvus_client.py`
- `database/mysql_client.py`
- `modules/memory.py`
- `modules/knowledge.py`

---

### 15.4 文本与编码问题

这是你当前项目里已经真实出现过的一类问题。

常见表现：

- 日志里的中文查询词变成乱码
- 文档打开显示乱码
- 模型上下文被脏文本污染

优先看：

- `utils/text_sanitizer.py`
- `modules/memory.py`
- `core/llm_client.py`
- `utils/logger.py`

你现在日志里就有一个很明显的现象：

- `query=` 后面的中文问题大量出现乱码

这说明至少要继续关注两件事：

- 请求进入日志前的编码/清洗是否统一
- 控制台、文件、接口链路里有没有某一段仍在错误解码

---

## 16. 日志怎么读最有效

日志文件位置：

- `logs/app.log`

日志初始化代码：

- `utils/logger.py`

### 16.1 当前日志已经覆盖了什么

现在日志里已经能看到这些关键信息：

- 应用启动地址
- 端口回退情况
- Redis 连接情况
- Milvus 连接情况
- Collection 是否加载成功
- 短期记忆是否读写成功
- 长期记忆是否检索成功
- 长期记忆是否写入成功
- 知识库检索是否命中
- LLM 调用的是哪个 provider / model / endpoint

这说明当前日志基础其实已经够用来排第一轮问题。

---

### 16.2 建议你先会看这几种日志

#### 启动成功类

例如：

- `Redis(remote) connection_ready`
- `Milvus(remote) connection_ready`
- `Milvus(remote) collection_loaded`

说明：

- 远程 Redis 连上了
- 远程 Milvus 连上了
- 指定集合已经可搜索

#### 端口冲突类

例如：

- `Configured port 8001 is unavailable, falling back to 8002.`

说明：

- 不是应用没启动
- 而是端口冲突后自动切换了端口

#### 对话上下文类

例如：

- `history_loaded`
- `Long-memory search`
- `search collection=role_knowledge`

说明：

- 短期记忆有没有取到
- 长期记忆有没有命中
- 知识库有没有命中

#### 写回类

例如：

- `message_saved`
- `documents_upserted`
- `Long-memory stored`

说明：

- 一轮对话结束后，是否真的写回了记忆系统

---

### 16.3 目前日志里已经暴露出的两个重点问题

#### 问题 1：中文查询日志存在乱码

现象：

- `query=` 后面很多中文被写成乱码

影响：

- 虽然不一定影响检索本身
- 但会明显影响排查效率

这类问题后续应该继续沿着下面链路查：

- 前端请求编码
- FastAPI 请求体解析
- 日志打印前的文本清洗
- 控制台编码与文件编码是否一致

#### 问题 2：启动阶段有重复初始化痕迹

现象：

- 同一轮启动附近出现两组相似的 `Redis/Milvus/Embedding/Database initialized` 日志

原因：

- 之前 `uvicorn.run("main:app", ...)` 会再次导入模块，可能导致服务对象初始化重复

我已经在 `main.py` 里把启动改成直接传 `app` 对象，这样更稳：

- `uvicorn.run(app, ...)`

这样能减少重复导入带来的重复初始化和重复日志。

---

## 17. 数据文件分别是干什么的

这部分非常关键，因为很多“问题”最后不是代码逻辑错，而是数据源、存储层、降级文件和真实存储的关系没分清。

### 17.1 种子数据文件

位置：

- `data/seed/roles.json`
- `data/seed/knowledge_documents.json`
- `data/seed/eval_dataset.json`

作用：

- `roles.json`：角色原始定义
- `knowledge_documents.json`：知识库原始内容
- `eval_dataset.json`：评测样本

它们属于：

- 系统初始输入数据

不是运行时聊天记录。

---

### 17.2 运行期数据文件

位置：

- `data/storage/app.db`
- `data/storage/redis_store.json`
- `data/storage/milvus_store.json`
- `data/storage/demo_seed_version.txt`

作用：

- `app.db`：用户和角色基础信息
- `redis_store.json`：Redis 不可用时的短期记忆降级文件
- `milvus_store.json`：Milvus 不可用时的向量存储降级文件
- `demo_seed_version.txt`：标记当前演示数据是否已经初始化过

你要特别区分：

- `app.db` 是主要基础库
- `redis_store.json` 和 `milvus_store.json` 不是主路径，而是降级路径

也就是说，只有当真实 Redis / Milvus 不可用时，它们才是关键现场。

---

### 17.3 日志文件

位置：

- `logs/app.log`

这是：

- 第一排查入口

不是存业务数据，但它记录了业务链路发生过什么。

---

### 17.4 容器卷数据

位置：

- `volumes/`

这里存的是：

- Milvus
- MinIO
- etcd

这些更偏基础设施层。

如果你只是排聊天逻辑，通常先不用钻这里。

只有在下面场景才优先看：

- 容器数据损坏
- Milvus 启动异常
- 向量库底层状态不一致

---

## 18. 结构框架应该怎么理解

如果只用一句话概括现在这套结构：

- `main.py` 负责接请求，`ChatService` 负责编排，`MemoryManager` 和 `Retriever` 提供上下文，`LLMClient` 负责生成，`database/*` 负责落库。

### 18.1 四层结构图

你可以把项目先拆成这 4 层：

1. 接口层
2. 业务编排层
3. 核心能力层
4. 存储层

对应关系：

```text
接口层
  main.py

业务编排层
  modules/chat.py
  modules/memory.py
  modules/knowledge.py
  modules/role_prompts.py

核心能力层
  core/llm_client.py
  core/retriever.py
  core/embedding.py
  core/rerank.py

存储层
  database/mysql_client.py
  database/redis_client.py
  database/milvus_client.py
  data/storage/*
```

---

### 18.2 现在这套结构里最关键的装配点

入口装配点：

- `main.py` 里的 `build_services()`

这个函数非常重要，因为它把：

- MySQLClient
- RedisClient
- MilvusClient
- EmbeddingService
- RerankService
- Retriever
- MemoryManager
- LLMClient
- KnowledgeManager
- ChatService

全部接起来了。

如果你后面要改框架，不管是换存储、换模型、换检索逻辑，几乎都绕不开这里。

---

### 18.3 结构上最值得继续优化的点

从当前项目状态看，后面最值得继续补强的是这几件事：

1. 问题排查路径再标准化
2. 日志字段再结构化
3. 编码问题统一收口
4. 文档把“运行态”和“设计态”区分更清楚

具体说：

- 现在日志可读，但还不是严格结构化日志
- 现在能降级，但真实存储和降级存储的切换现场还可以写得更明显
- 现在文档有设计图，但缺一份更偏运维/排障视角的索引

这一节补的内容，就是在帮你补这块。

---

## 19. 你现在排项目，建议按这个顺序

如果你现在就是要处理“问题、日志、数据文件、结构框架”，最稳的顺序是：

1. 先看 `logs/app.log`
2. 再确认当前走的是远程存储还是本地降级存储
3. 再确认问题属于启动、对话、存储、还是编码问题
4. 再顺着对应模块看代码
5. 最后再决定要不要改数据文件或改结构

你可以把它记成一句话：

```text
先看日志定位步骤，再看数据确认现场，最后回代码改结构
```

---

## 20. 最后给你一个当前项目的处理重点结论

结合你现在这个项目的状态，最值得优先处理的不是“再加新功能”，而是先把下面 4 件事打稳：

1. 把日志里的中文乱码问题继续查清
2. 明确当前每次运行到底走的是 Redis/Milvus 还是本地降级文件
3. 把数据文件职责彻底分清，避免混淆“种子数据”“运行数据”“降级数据”
4. 按 `main.py -> chat.py -> memory/retriever -> llm_client/database` 这条链路建立固定排查习惯

这样后面你不管是继续做：

- 功能开发
- Bug 修复
- 结构重构
- 文档完善

都会顺很多。
