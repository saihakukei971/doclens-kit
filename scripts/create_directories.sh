#!/bin/bash
# ディレクトリ構造を作成するスクリプト

# 基本ディレクトリ
mkdir -p app/api
mkdir -p app/core
mkdir -p app/models
mkdir -p app/services
mkdir -p app/utils
mkdir -p app/web/static/css
mkdir -p app/web/static/js
mkdir -p app/web/templates
mkdir -p config
mkdir -p data/documents
mkdir -p data/archives
mkdir -p logs
mkdir -p models
mkdir -p backups
mkdir -p scripts

# __init__.py の作成
touch app/__init__.py
touch app/api/__init__.py
touch app/core/__init__.py
touch app/models/__init__.py
touch app/services/__init__.py
touch app/utils/__init__.py
touch app/web/__init__.py

# API ファイル
touch app/api/documents.py
touch app/api/search.py
touch app/api/system.py

# コアファイル
touch app/core/config.py
touch app/core/database.py
touch app/core/logger.py
touch app/core/security.py

# モデルファイル
touch app/models/document.py
touch app/models/search.py

# サービスファイル
touch app/services/document_processor.py
touch app/services/ocr_service.py
touch app/services/classifier.py
touch app/services/search_service.py
touch app/services/archiver.py

# ユーティリティファイル
touch app/utils/file_utils.py
touch app/utils/text_utils.py

# Webファイル
touch app/web/templates/index.html
touch app/web/static/css/styles.css
touch app/web/static/js/main.js

# メインアプリケーションファイル
touch app/main.py

# 設定ファイル
touch config/default.toml
touch config/classifier_config.yaml

# スクリプト
touch scripts/archive_task.py
touch scripts/backup.py
touch scripts/deploy.sh
touch scripts/initialize.py
touch scripts/setup_cron.sh
touch scripts/vacuum_task.py

# プロジェクトファイル
touch docker-compose.yml
touch Dockerfile
touch Makefile
touch requirements.txt
touch README.md
touch .gitignore

# 実行権限の付与
chmod +x scripts/archive_task.py
chmod +x scripts/backup.py
chmod +x scripts/deploy.sh
chmod +x scripts/initialize.py
chmod +x scripts/setup_cron.sh
chmod +x scripts/vacuum_task.py
chmod +x scripts/create_directories.sh

# .gitkeep ファイルの作成（空ディレクトリをGitで保持するため）
touch data/.gitkeep
touch data/documents/.gitkeep
touch data/archives/.gitkeep
touch logs/.gitkeep
touch models/.gitkeep
touch backups/.gitkeep

echo "ディレクトリ構造の作成が完了しました。"