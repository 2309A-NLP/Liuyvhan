from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import SETTINGS
from database.milvus_client import MilvusClient
from utils.logger import get_logger


def main() -> None:
    logger = get_logger("init_milvus")
    client = MilvusClient(SETTINGS, logger)
    client.ensure_collection(SETTINGS.knowledge_collection)
    client.ensure_collection(SETTINGS.long_memory_collection)
    if client.storage_mode == "milvus":
        print(f"Milvus collections initialized on {SETTINGS.milvus_uri}")
    else:
        print(f"Milvus local fallback initialized at {SETTINGS.local_milvus_path}")


if __name__ == "__main__":
    main()
