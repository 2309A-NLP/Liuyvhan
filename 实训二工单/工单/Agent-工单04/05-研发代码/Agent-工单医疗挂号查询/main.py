"""兼容 PyCharm 现有运行配置的根入口。"""

from __future__ import annotations

import uvicorn

from app.config import settings


def print_startup_urls() -> None:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    service_url = f"http://{settings.app_host}:{settings.app_port}"
    docs_url = f"{service_url}/docs"
    print("=" * 60, flush=True)
    print(f"浏览器访问地址: {service_url}", flush=True)
    print(f"接口文档地址: {docs_url}", flush=True)
    print("=" * 60, flush=True)


def main() -> None:
    """工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理任务。"""

    print_startup_urls()
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)


if __name__ == "__main__":
    main()
