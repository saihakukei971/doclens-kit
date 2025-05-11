#!/usr/bin/env python3
# scripts/initialize.py
"""
Initialization script for Business Data Integration Hub.
Creates necessary directories, initializes the database, and sets up configuration.
"""

import os
import sys
import asyncio
import argparse
import yaml
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.logger import log
from app.core.database import init_db, close_db


async def create_directories():
    """Create necessary directories if they don't exist."""
    directories = [
        "data",
        "data/documents",
        "data/archives",
        "logs",
        "models",
        "config",
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        log.info(f"ディレクトリ作成: {directory}")


async def create_default_config():
    """Create default configuration files if they don't exist."""
    # Default TOML config
    default_toml = Path("config/default.toml")
    if not default_toml.exists():
        with open(default_toml, "w", encoding="utf-8") as f:
            f.write("""# Default configuration for Business Data Integration Hub

# Database settings
DATABASE_URL = "sqlite:///data/documents.db"

# Storage paths
DOCUMENT_PATH = "data/documents"
ARCHIVE_PATH = "data/archives"

# Upload settings
UPLOAD_SIZE_LIMIT = 2147483648  # 2GB
ALLOWED_MIMETYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv"
]

# OCR settings
OCR_ENABLED = true
OCR_LANGUAGE = "jpn+eng"  # Japanese + English
# TESSERACT_CMD = "/usr/bin/tesseract"  # Uncomment if needed

# Archive settings
# ARCHIVE_ZIP = true  # Uncomment to enable ZIP creation
# REMOVE_AFTER_ZIP = false  # Uncomment to remove original files after ZIP

# Web interface settings
WEB_ENABLED = true
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000

# Logging settings
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Security settings
# ALLOWED_IPS = [
#     "127.0.0.1",
#     "192.168.1.0/24"
# ]
""")
        log.info(f"設定ファイル作成: {default_toml}")

    # Classifier config
    classifier_config = Path("config/classifier_config.yaml")
    if not classifier_config.exists():
        with open(classifier_config, "w", encoding="utf-8") as f:
            f.write("""# Document type classification configuration

document_types:
  - name: invoice  # 請求書
    keywords: ['請求書', '御請求書', 'インボイス', '支払い', 'Invoice']
    patterns:
      - field: 'amount'
        regex: '合計.*?([0-9,]+)円'
      - field: 'invoice_date'
        regex: '(発行日|請求日)[：:]\s*(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2})'
      - field: 'due_date'
        regex: '(お支払期限|支払期限)[：:]\s*(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2})'
      - field: 'company'
        regex: '(株式会社|有限会社)([^\n\r]{1,20})'
      - field: 'invoice_number'
        regex: '(請求書番号|No)[.：:]\s*([A-Za-z0-9\-]{1,20})'

  - name: quotation  # 見積書
    keywords: ['見積書', '御見積書', 'お見積り', 'Quotation', '見積金額']
    patterns:
      - field: 'amount'
        regex: '(見積金額|合計).*?([0-9,]+)円'
      - field: 'quotation_date'
        regex: '(発行日|見積日)[：:]\s*(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2})'
      - field: 'valid_until'
        regex: '(有効期限|見積有効期限)[：:]\s*(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2})'
      - field: 'company'
        regex: '(株式会社|有限会社)([^\n\r]{1,20})'

  - name: receipt  # 領収書
    keywords: ['領収書', '領収証', 'Receipt', 'レシート']
    patterns:
      - field: 'amount'
        regex: '(金額|合計|領収金額).*?([0-9,]+)円'
      - field: 'receipt_date'
        regex: '(発行日|日付)[：:]\s*(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2})'
      - field: 'company'
        regex: '(株式会社|有限会社)([^\n\r]{1,20})'

# Default extraction patterns for all document types
default_patterns:
  - field: 'date'
    regex: '(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2})'
  - field: 'amount'
    regex: '([0-9,]+)円'
  - field: 'company'
    regex: '(株式会社|有限会社)([^\n\r]{1,20})'
""")
        log.info(f"分類器設定ファイル作成: {classifier_config}")


async def initialize_database():
    """Initialize database and create tables."""
    try:
        await init_db()
        log.info("データベース初期化完了")
    finally:
        await close_db()


async def main():
    parser = argparse.ArgumentParser(description="Initialize Business Data Integration Hub")
    parser.add_argument("--force", "-f", action="store_true", help="Force initialization")
    args = parser.parse_args()

    try:
        log.info("初期化処理開始")

        # Check if already initialized
        if os.path.exists("data/documents.db") and not args.force:
            log.warning("データベースが既に存在します。--force オプションを使用して強制初期化できます。")
            return

        # Create directories
        await create_directories()

        # Create default config
        await create_default_config()

        # Initialize database
        await initialize_database()

        log.info("初期化処理完了")

    except Exception as e:
        log.error(f"初期化処理エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())