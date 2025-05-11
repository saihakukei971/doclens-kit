#!/usr/bin/env python3
# scripts/vacuum_task.py
"""
Database vacuum task script to be run periodically (e.g., via cron).
Optimizes the database by running VACUUM.
"""

import os
import sys
import asyncio

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.logger import log
from app.services.archiver import vacuum_database


async def main():
    try:
        log.info("データベース最適化タスク開始")

        # Run vacuum
        await vacuum_database()

        log.info("データベース最適化タスク完了")

    except Exception as e:
        log.error(f"データベース最適化タスクエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())