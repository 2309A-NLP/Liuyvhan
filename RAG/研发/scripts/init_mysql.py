from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import SETTINGS
from database.mysql_client import MySQLClient
from utils.logger import get_logger


def main() -> None:
    logger = get_logger("init_mysql")
    client = MySQLClient(SETTINGS, logger)
    client.init_schema()
    print(f"MySQL logical schema initialized at {SETTINGS.sqlite_path}")


if __name__ == "__main__":
    main()
