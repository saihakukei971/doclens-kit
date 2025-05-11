#!/usr/bin/env python3
# scripts/backup.py
"""
Backup script to be run periodically (e.g., via cron).
Creates a backup of the database and configuration.
"""

import os
import sys
import asyncio
from datetime import datetime
import shutil
import zipfile
import sqlite3

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.logger import log
from app.core.config import settings


async def main():
    try:
        log.info("バックアップタスク開始")

        # Create backup directory
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)

        # Get current timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Backup database
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_path):
            # Create a copy of the database
            backup_db_path = os.path.join(backup_dir, f"documents_{timestamp}.db")

            # Use SQLite's backup mechanism
            await asyncio.to_thread(_backup_sqlite_db, db_path, backup_db_path)

            log.info(f"データベースバックアップ完了: {backup_db_path}")

        # Backup configuration
        config_dir = "config"
        if os.path.exists(config_dir):
            backup_config_path = os.path.join(backup_dir, f"config_{timestamp}.zip")

            # Create ZIP file
            with zipfile.ZipFile(backup_config_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(config_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(config_dir))
                        zipf.write(file_path, arcname)

            log.info(f"設定バックアップ完了: {backup_config_path}")

        # Clean old backups (keep last 7 days)
        await asyncio.to_thread(_clean_old_backups, backup_dir, 7)

        log.info("バックアップタスク完了")

    except Exception as e:
        log.error(f"バックアップタスクエラー: {e}")
        sys.exit(1)


def _backup_sqlite_db(source_path, dest_path):
    """
    Create a backup of the SQLite database.

    Args:
        source_path: Source database path
        dest_path: Destination database path
    """
    # Connect to source database
    source_conn = sqlite3.connect(source_path)

    # Connect to destination database
    dest_conn = sqlite3.connect(dest_path)

    # Create a backup
    source_conn.backup(dest_conn)

    # Close connections
    source_conn.close()
    dest_conn.close()


def _clean_old_backups(backup_dir, days_to_keep):
    """
    Clean old backups, keeping only the specified number of days.

    Args:
        backup_dir: Backup directory
        days_to_keep: Number of days to keep
    """
    now = datetime.now()

    for filename in os.listdir(backup_dir):
        file_path = os.path.join(backup_dir, filename)

        # Skip if not a file
        if not os.path.isfile(file_path):
            continue

        # Get file creation time
        file_time = datetime.fromtimestamp(os.path.getctime(file_path))

        # Check if older than days_to_keep
        if (now - file_time).days > days_to_keep:
            os.remove(file_path)
            log.info(f"古いバックアップを削除: {file_path}")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())