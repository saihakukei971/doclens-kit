#!/usr/bin/env python3
# scripts/archive_task.py
"""
Archive task script to be run periodically (e.g., via cron).
Archives documents from the previous month.
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.logger import log
from app.services.archiver import create_archive, clean_old_archives, vacuum_database


async def main():
    try:
        log.info("アーカイブタスク開始")

        # Get previous month
        today = datetime.now()
        first_day = today.replace(day=1)
        last_month = first_day - timedelta(days=1)
        year = last_month.year
        month = last_month.month

        log.info(f"対象期間: {year}年{month}月")

        # Create archive
        archive_path = await create_archive(year, month)
        if archive_path:
            log.info(f"アーカイブ作成完了: {archive_path}")
        else:
            log.warning("アーカイブ作成失敗またはアーカイブ対象なし")

        # Clean old archives (keep last 12 months)
        await clean_old_archives(keep_count=12)

        # Vacuum database
        await vacuum_database()

        log.info("アーカイブタスク完了")

    except Exception as e:
        log.error(f"アーカイブタスクエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())