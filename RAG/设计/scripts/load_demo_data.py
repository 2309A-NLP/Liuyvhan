from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import SETTINGS
from core.embedding import EmbeddingService
from database.milvus_client import MilvusClient
from database.mysql_client import MySQLClient
from modules.knowledge import KnowledgeManager
from utils.logger import get_logger


def main() -> None:
    logger = get_logger("load_demo_data")
    mysql_client = MySQLClient(SETTINGS, logger)
    mysql_client.init_schema()
    milvus_client = MilvusClient(SETTINGS, logger)
    embedding_service = EmbeddingService(SETTINGS, logger)
    manager = KnowledgeManager(SETTINGS, mysql_client, milvus_client, embedding_service, logger)
    result = manager.reload_demo_data()
    print(result)


if __name__ == "__main__":
    main()
