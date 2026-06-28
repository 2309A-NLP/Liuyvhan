#!/usr/bin/env python3
"""
Initialize the schedule_reminder database with the local Windows Python runtime.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import SETTINGS
from database import init_database


if __name__ == "__main__":
    init_database()
    print("Database initialized successfully.")
