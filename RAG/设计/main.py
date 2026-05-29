from __future__ import annotations
# 更新
import json
import socket
"""
python 内置的网络通信库 让程序之间通过网络收发数据 
但是在这段代码中 是用来检查端口是否被占用的
"""
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from config import SETTINGS   # 提供所以配置参数
from core.embedding import EmbeddingService
from core.llm_client import LLMClient
from core.rerank import RerankService
from core.retriever import Retriever
from database.milvus_client import MilvusClient
from database.mysql_client import MySQLClient
from database.redis_client import RedisClient
from models.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    KnowledgeReloadResponse,
    PDFImportStatusResponse,
    RoleProfile,
    SessionHistoryResponse,
    User,
    UserCreate,
)
from modules.chat import ChatService
from modules.knowledge import KnowledgeManager
from modules.memory import MemoryManager
from modules.pdf_auto_import import PDFAutoImportManager
from utils.logger import get_logger

# 这一部分时全局变量
logger = get_logger("app")
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
"""
===STATIC_DIR = FRONTEND_DIR / "static"===
FRONTEND_DIR --- 前端文件夹
/ "static"   --- 是 pathlib.Path 的路径拼接写法
最后得到的就是：
项目根目录/frontend/stati --- 我的静态资源文件，都放在 frontend/static 这个目录里  
图片
css
js
favicon
图标文件
"""
STATIC_DIR = FRONTEND_DIR / "static"
FAVICON_PATH = STATIC_DIR / "favicon.svg"


"""
===_find_available_port===
#自动找到可用的端口号
作用：从首选的端口开始，依次检查每个端口是否被占用 第一个找到空闲的端口号 
避免端口被占用的错误
"""
#                       本机地址      端口号                  尝试次数20
def _find_available_port(host: str, preferred_port: int, max_attempts: int = 20) -> int: #这是约定私有函数（技术上不够私有） 可以在外部调用 但是会被警告 __双下划线是真正私有函数 无法被外部调用
    for port in range(preferred_port, preferred_port + max_attempts): # 从首选端口开始 依次检查 最多检查20个不包含最后一个
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock: # 创建一个专门检测IPv4-TCP端口的工具
            #使用           IPv4地址           TCP协议（可靠的面对面的通信协议）
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # 优化工具 允许立即重用端口  操作系统给端口60秒冷却时间  防止旧数据包干扰新连接
            # socket.SOL_SOCKET --- 指定修改的层级  告诉系统"我要改 socket 本身的设置"
            # SO_REUSEADDR  ----    指定修改的功能  系统"我要改的具体是'重用地址'这个功能"，1 告诉系统"把这个功能打开"
            try:
                sock.bind((host, port))
                # bind -- 占用 绑定 ，
                # 为什么是双括号 - 内括号是表示的元组
                #               外扩号是bind的语法要求-
            except OSError:
                continue
        if port != preferred_port: # 判断当前端口（当前端口）是不是首选端口（用户想要的）
            logger.warning(
                "Configured port %s is unavailable, falling back to %s.",
                preferred_port,
                port,
            )
        return port
    raise RuntimeError(
        f"No available port found in range {preferred_port}-{preferred_port + max_attempts - 1}."
    )
#   报错 当循环完成 还是没有找到可用的端口号 直接报错

"""
===_detect_lan_ip===
# 自动检测本机局域网IP地址，让其他网络设备也可以访问服务
两种方法：
链接外部DNS(8.8.8.8)获取本机IP
通过主机名获取IP
"""
def _detect_lan_ip() -> str | None:  #  这个函数要么返回字符串，要么返回空值(None)。‘|’ 或
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock: # 创建
            # socket.AF_INET --- 使用IPv4地址
            # socket.SOCK_DGRAM --- 使用UDP协议
            # with 的作用：用完自动关闭socket 即使出错自动清理
            sock.connect(("8.8.8.8", 80))
            # connect -- 建立连接   告诉socket 要连接到哪个远程服务器。
            # 8.8.8.8 是Google的公共DNS，几乎永远在线  回复速度快，全球可访问
            ip = sock.getsockname()[0]
            # getsockname 返回 socket 绑定的本地地址
            # sock.getsockname() 返回内容('192.168.1.100', 54321) 紧要192.168.1.100 这一部分

            if ip and not ip.startswith("127."):# ip 不为空 and  IP 地址不是127 开头
            # startswith() 判断字符串是否以指定内容开头
                return ip
    except OSError:
        pass

    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    return None

"""
===_log_access_urls===
在控制台打印出服务的访问地址，告诉用户怎么打开网页。
之所以控制台会重复打印两编 是因为运行main.py 文件是一遍
运行 if __name__ == "__main__": 函数还是一遍
"""
def _log_access_urls(host: str, port: int) -> None:
    logger.info("Open the site root in a browser, not /static.")
    logger.info("Local URL: http://127.0.0.1:%s/", port)
    logger.info("Workspace URL: http://127.0.0.1:%s/workspace", port)
    if host == "0.0.0.0":
        lan_ip = _detect_lan_ip()
        if lan_ip:
            logger.info("LAN URL: http://%s:%s/", lan_ip, port)
            logger.info("LAN workspace URL: http://%s:%s/workspace", lan_ip, port)
        else:
            logger.info("LAN URL: unavailable, check your network adapter IP.")
    else:
        logger.info("Configured URL: http://%s:%s/", host, port)

"""
build_services - 函数作用
就是把项目里要用到的各种“工具”和“负责人”都创建出来，再组装成一套能工作的系统
这些工具和负责人在代码里早就已经定义好了 把它们实例化并组装起来

"""
def build_services() -> dict[str, object]:# 返回类型为字典 str - 键   object - 任意类型

    """

    """
    """
    第一层 - 创建底层客户端
    SETTINGS : 是一个大的配置工具箱（包含所有配置）  每一个函数会各取所需
    
    """
    # 实例化对象
    # 管理用户 和 角色
    mysql_client = MySQLClient(SETTINGS, logger)
    # 管理短期对话
    redis_client = RedisClient(SETTINGS, logger)
    # 管理长期对话 和 知识库
    milvus_client = MilvusClient(SETTINGS, logger)

    """
    创建核心能力组件
    """
    embedding_service = EmbeddingService(SETTINGS, logger) # 文本转向量
    rerank_service = RerankService(SETTINGS, logger)       # 重排序 Milvus 召回一批候选之后 通过相关性排序 选出最优答案

    """
    创建中层业务组件
    """
    # 检索器
    retriever = Retriever(SETTINGS, milvus_client, embedding_service, rerank_service, logger)
    #                     配置信息   向量数据库       向量化服务（文本-向量）  重排序（优化结果）  日志

    # 记忆管理器 - 管理对话历史，维护上下文记忆
    memory_manager = MemoryManager(SETTINGS, redis_client,       milvus_client,      embedding_service, logger)
    #                               配置信息   Redis缓存（存短期记忆）向量数据库（存长期记忆） 向量化服务（记忆向量化）
    #   短期记忆 （按时间顺序）无需文本转向量 直接存入 Redis
    #   长期记忆  (按照语义相似的搜索)文本转向量 存入Milvus

    """
    大模型客户端
    负责调用真正的大模型API  
    LLMClient 负责与大语言模型（如 GPT-4、ChatGLM 等）通信，发送提示词并获取回答
    """
    llm_client = LLMClient(SETTINGS, logger)

    """
    知识库管理员 负责 存入数据到知识库中
    """
    knowledge_manager = KnowledgeManager(
        SETTINGS,
        mysql_client,
        milvus_client,
        embedding_service,
        logger,
    )

    pdf_auto_import_manager = PDFAutoImportManager(
        SETTINGS,
        mysql_client,
        milvus_client,
        embedding_service,
        logger,
    )

    """
    配置能完成这整套流程（长短期记忆并调用大模型）的总指挥对象 
    """
    chat_service = ChatService(
        SETTINGS,    # 配置 --- 检索数量 记忆轮数 模型参数等
        mysql_client,# Mysql 数据库 --- 查询角色信息
        retriever,   #            --- 查询知识库
        memory_manager, #         --- 查/写长短期记忆
        llm_client,     #         --- 调用大模型
        logger,
    )

    """
    把前面创建好的所有 对象 统一打包返回 让后面的 FastAPI 应用可以随时按名字取用它们
    这些对象在 build_services 函数中 是内部变量 return 输出之后 可以在外部随意取用
    """
    return {
        "mysql_client": mysql_client,
        "redis_client": redis_client,
        "milvus_client": milvus_client,
        "embedding_service": embedding_service,
        "rerank_service": rerank_service,
        "retriever": retriever,
        "memory_manager": memory_manager,
        "llm_client": llm_client,
        "knowledge_manager": knowledge_manager,
        "pdf_auto_import_manager": pdf_auto_import_manager,
        "chat_service": chat_service,
    }


def create_app() -> FastAPI:
    """
    创建所有服务对象
    把数据库客户端、记忆管理器、检索器、知识库管理器、聊天总指挥等对象全部创建出
    """
    services = build_services()

    """
    规定 FastAPI 启动时要先做什么初始化工作
    """
    # @asynccontextmanager - 装饰器 - 将函数变成“异步上下文管理器”
    # async 异步函数  --- 更高的并发利用率  更少的空等浪费
    # 像 FastAPI 这种 Web 框架，后端经常会同时遇到很多请求：
    # A 用户在请求聊天
    # B 用户在请求历史记录
    # C 用户在请求角色列表

    # 如果全是同步方式，某个请求一旦卡住：
    # 其他请求也更容易跟着堵
    # 如果是异步方式，框架就可以在等待过程中切换去处理别的请求。

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # 应用启动时只做两件关键初始化：
        # 1. 建好基础表结构
        # 2. 确保演示角色和知识库已装载
        services["mysql_client"].init_schema()
        services["knowledge_manager"].initialize_demo_data()
        auto_import_task = None
        if SETTINGS.pdf_auto_import_enabled:
            auto_import_task = asyncio.create_task(_run_pdf_auto_import(services))
        yield
        if auto_import_task and not auto_import_task.done():
            auto_import_task.cancel()
        # yield - 是生命周期分界点 表示前面部分执行完之后 在执行后面部分
    app = FastAPI(  # 创建FastAPL应用 名称为app
        # 下面这部部分是这个app 简单的说明信息 名字 版本 简介
        title=SETTINGS.app_name,
        version=SETTINGS.app_version,
        summary="轻量级 RAG 角色扮演系统，默认支持 CPU 与本地降级模式。",
        lifespan=lifespan,  # 在告诉后端 你启动前做哪些准备
    )
    app.state.services = services   # services 这个是之前的创建的对象  现在放在app后端程序保存起来 在后端方便取用
    # 将服务对象挂到app.state成为共享对象  这样后面任何请求只要拿到 request.app，就能继续找到：request.app.state.services
    # app.state可以理解为 FastAPI 应用自己的共享储物柜
    # 为什么要放在aqq 不是已经在后端了吗？？？
    # 当下这下对象 还是在create_app函数中  属于局部变量
    # 处理前端的请求时 由下面的路由函数来执行 路由函数的路径时request.app  所有请求都通过 request.app.state 取服务
    # 把这份服务字典挂到 app 这个应用对象上
    # 让整个应用后面都能通过 app 找到它
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")# 存储静态文件的路径
    # StaticFiles(directory=STATIC_DIR) --- 创建一个静态文件服务器，它专门去 STATIC_DIR 这个目录里找文件。
    # /static 是网站给静态文件开的统一入口，浏览器请求某个静态文件时，后端会根据这个路径去本地静态目录找到文件并返回
    # app.mount("/static") -- 把本地这个目录映射到网址路径  把这个静态文件服务器挂到网站的 /static 路径下面
    # 例子： 你在网页里如果要加载一张图片
    # 浏览器就会去请求 /static/... 这个路径              <img src="/static/avatar.png">
    # 后端收到这个请求后
    # 就会去本地对应的 frontend/static 文件夹里找这个文件  http://127.0.0.1:8001/static/avatar.png
    # 找到后再返回给浏览器

    def get_service(request: Request, name: str):
        # Request --- 当前这次 HTTP 请求对象
        # name --- 想取的服务名称  例如mysql_client
        # 所有路由都从 app.state 里取服务，避免在每个接口里重复 new 对象。
        return request.app.state.services[name]
        # 去应用对象 app 身上，找到 services 这份服务字典，再按名字把对应对象拿出来返回

    """
    这些函数统称路由函数 --- 也就是后端专门用来接受并处理浏览器/前端请求的入口函数
    当前端发送请求过来
    后端根据请求路径找到对应路由函数
    这个函数再决定怎么处理
    最后把结果返回给前端
    
    """
    """
    页面路由 VS API路由
    页面路由 -- 这个路由返回时网页文件
    例如：@app.get("/", include_in_schema=False)  @app.get("/workspace", include_in_schema=False)
    也就是说 当浏览器访问这些地址 后端给它是网页页面
    比如：
    访问 /
    打开首页
    访问 /workspace
    打开工作台页面
    
    API 路由 -- 返回是数据
    API 路由负责“页面背后的数据交互和功能处理
    """

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/workspace", include_in_schema=False)
    async def workspace() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "workspace.html")

    """
    静态资源访问入口
    """
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> RedirectResponse:
        return RedirectResponse(url="/static/favicon.svg", status_code=307)

    """
    查看系统运行状态 返回状态数据
    """
    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        memory_manager: MemoryManager = get_service(request, "memory_manager")
        return HealthResponse(
            status="ok",
            llm_provider=SETTINGS.llm_provider,
            embedding_backend=SETTINGS.embedding_backend,
            storage_mode=memory_manager.storage_mode,
        )

    """
    获取角色列表 返回角色数据
    """
    @app.get("/roles", response_model=list[RoleProfile])
    async def list_roles(request: Request) -> list[RoleProfile]:
        mysql_client: MySQLClient = get_service(request, "mysql_client")
        return mysql_client.list_roles()


    """
    创建用户 前端提交用户信息，后端返回创建后的用户数据。
    """
    @app.post("/users", response_model=User)
    async def create_user(payload: UserCreate, request: Request) -> User:
        mysql_client: MySQLClient = get_service(request, "mysql_client")
        return mysql_client.create_user(payload)


    """
    普通聊天接口  一次性返回完整答案
    """
    @app.post("/chat", response_model=ChatResponse)
    # 前端发送请求 调用普通接口 POST /chat
    # FastAPI根据路径匹配路由  当请求方法：POST 请求路径：/chat
    # 自动匹配这段路由函数   astAPI 自动解析请求体
    # 前端发来的是 JSON。 FastAPI 会按 ChatRequest 这个模型把它解析成一个对象，交给参数：

    # response_model=ChatResponse --- 这个接口返回前端的数据，应该符合 ChatResponse 这个格式
    async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
        # payload: ChatRequest --- 前端发来 JSON 数据 会被 FastAPI 解析成一个 ChatRequest 对象
        # request --- 是整个 HTTP 请求对象 里面除了请求体，还可以包含很多别的信息，比如：请求路径 请求方法 请求头  客户端信息 当前所属的 app  路由上下文
        # 运行过程：
            # 先通过 request 从应用的共享服务仓库里取出 chat_service 对象工具，再把前端发来的 payload 交给chat_service处理。
        chat_service: ChatService = get_service(request, "chat_service")
        # get_service --- 函数就是取工具对象的函数 （request, "chat_service"）--- 我现在要从服务仓库里拿名字叫 chat_service 的那个对象
        # 专业术语：通过当前请求找到应用里的服务仓库，从里面取出已经创建好的 chat_service 对象，并保存到当前函数里的 chat_service 变量中。
        try:
            # 非流式接口：后端一次性拿到完整答案后再返回。
            return chat_service.chat(payload)
            # ChatService 对象里的 chat() 方法，并把本次聊天请求数据 payload 传进去。
            # 把前端发来的聊天请求交给 ChatService 处理，等它完整跑完聊天主流程后，再把返回结果直接交还给前端
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    """
    流式 API 路由
    负责边生成边返回数据
    """
    @app.post("/chat/stream")
    async def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
        chat_service: ChatService = get_service(request, "chat_service")
        try:
            stream = chat_service.stream_chat(payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        def encode_events():
            # 前端使用 NDJSON 逐行消费事件：
            # chunk 表示增量文本，done 表示整轮结束。
            for event in stream:
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(encode_events(), media_type="application/x-ndjson")

    """
    获取某个会话的历史消息
    """
    @app.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse)
    async def get_history(session_id: str, request: Request) -> SessionHistoryResponse:
        memory_manager: MemoryManager = get_service(request, "memory_manager")
        history = memory_manager.get_short_memory(session_id)
        return SessionHistoryResponse(session_id=session_id, messages=history)

    """
    重新加载角色和知识库数据
    """
    @app.post("/knowledge/reload", response_model=KnowledgeReloadResponse)
    async def reload_knowledge(request: Request) -> KnowledgeReloadResponse:
        knowledge_manager: KnowledgeManager = get_service(request, "knowledge_manager")
        result = knowledge_manager.reload_demo_data()
        return KnowledgeReloadResponse(**result)

    @app.get("/pdf/import-status", response_model=PDFImportStatusResponse)
    async def pdf_import_status(request: Request) -> PDFImportStatusResponse:
        manager: PDFAutoImportManager = get_service(request, "pdf_auto_import_manager")
        result = manager.get_status()
        return PDFImportStatusResponse(**result)

    return app

"""查看 PDF 自动导入状态"""
"""启动时自动扫描 data/raw_pdfs/
自动解析 PDF、切块、embedding、写入 Milvus"""
async def _run_pdf_auto_import(services: dict[str, object]) -> None:
    manager: PDFAutoImportManager = services["pdf_auto_import_manager"]  # type: ignore[assignment]
    # 从 services 字典中拿出键名为 "pdf_auto_import_manager" 的对象  把它赋值给变量 manager
    try:
        await asyncio.to_thread(manager.run_once)
    except asyncio.CancelledError:
        logger.info("PDF auto import task cancelled.")
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("PDF auto import background task failed. error=%s", exc)


app = create_app()

"""
if __name__ == "__main__": - 它不是函数 是python 中模块入口保护写法
在做一个运行时判断 如果当前模块被主文件运行 就执行 如果不是就不执行if __name__ == "__main__" 部分下的内容
只有在运行当前文件 
"""
if __name__ == "__main__":
    import uvicorn

    port = _find_available_port(SETTINGS.host, SETTINGS.port)
    _log_access_urls(SETTINGS.host, port)
    uvicorn.run(
        "main:app",
        host=SETTINGS.host,
        port=port,
        reload=False,
    )
