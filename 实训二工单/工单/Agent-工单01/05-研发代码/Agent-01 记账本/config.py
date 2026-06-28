"""配置模块
工单编号：人工智能NLP-Agent数字人项目-01-记账本任务工单V1.1-20250206
"""

import socket
import sys


def get_mysql_host():
    """获取MySQL主机地址
    - Windows上运行：直接连127.0.0.1（MySQL在本机）
    - WSL/Linux上运行：自动检测Windows网关IP
    """
    if sys.platform == "win32":
        return "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            # WSL网关通常是x.x.x.1
            parts = ip.split(".")
            gateway = ".".join(parts[:-1]) + ".1"
            return gateway
    except Exception:
        return "127.0.0.1"


# MySQL 配置
MYSQL_CONFIG = {
    "host": get_mysql_host(),
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "account_book",
    "charset": "utf8mb4",
}

# 服务器配置
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8010

# 家庭成员
FAMILY_MEMBERS = ["爸爸", "妈妈", "女儿"]
