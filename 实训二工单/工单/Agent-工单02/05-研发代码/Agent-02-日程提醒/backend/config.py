"""
日程管家 - 配置文件
工单：人工智能 NLP-Agent 数字人项目-日程管家任务
"""

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """加载 .env 文件（如果存在）"""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


@dataclass(slots=True)
class Settings:
    # FastAPI 服务配置
    app_name: str = "日程管家"
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8012"))

    # MySQL 数据库配置
    _mysql_host: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("MYSQL_USER", "root")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "root")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "schedule_reminder")
    mysql_charset: str = os.getenv("MYSQL_CHARSET", "utf8mb4")

    # LLM 配置（硅基流动 SiliconFlow）
    llm_provider: str = os.getenv("LLM_PROVIDER", "siliconflow")
    llm_model_name: str = os.getenv(
        "LLM_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct"
    )
    llm_api_base: str = os.getenv(
        "LLM_API_BASE", "https://api.siliconflow.cn/v1"
    )
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_timeout: int = int(os.getenv("LLM_TIMEOUT", "30"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    llm_top_p: float = float(os.getenv("LLM_TOP_P", "0.9"))

    @property
    def mysql_host(self) -> str:
        """动态检测 WSL 环境下的 Windows 主机 IP"""
        host = self._mysql_host
        if host == "127.0.0.1":
            try:
                with open("/proc/version") as f:
                    if "microsoft" not in f.read().lower():
                        return host
                import subprocess
                result = subprocess.run(
                    ["ip", "route", "show", "default"],
                    capture_output=True, text=True, timeout=3
                )
                if result.returncode == 0 and result.stdout.strip():
                    gateway = result.stdout.strip().split()[2]
                    if gateway:
                        return gateway
            except Exception:
                pass
        return host


SETTINGS = Settings()
