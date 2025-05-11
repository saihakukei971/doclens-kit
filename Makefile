# Makefile for Business Data Integration Hub

# Variables
PYTHON = python3
PIP = pip
DOCKER = docker
DOCKER_COMPOSE = docker-compose
CONTAINER_NAME = data_hub

# Default target
.PHONY: help
help:
	@echo "業務データ統合ハブ - 開発タスク"
	@echo ""
	@echo "使用方法:"
	@echo "  make setup              環境のセットアップ"
	@echo "  make init               データベースと設定の初期化"
	@echo "  make run                開発サーバーの起動"
	@echo "  make docker-build       Dockerイメージのビルド"
	@echo "  make docker-up          Dockerコンテナの起動"
	@echo "  make docker-down        Dockerコンテナの停止"
	@echo "  make docker-logs        Dockerコンテナのログ表示"
	@echo "  make test               単体テストの実行"
	@echo "  make lint               コードの静的解析"
	@echo "  make format             コードのフォーマット"
	@echo "  make clean              一時ファイルの削除"
	@echo "  make backup             バックアップの作成"
	@echo "  make docs               ドキュメントの生成"
	@echo ""
	@echo "本番環境用:"
	@echo "  make prod-up            本番環境のコンテナ起動"
	@echo "  make prod-deploy        本番環境へのデプロイ"
	@echo "  make cron-setup         cronジョブのセットアップ"

# Setup
.PHONY: setup
setup:
	@echo "環境をセットアップしています..."
	$(PIP) install -r requirements.txt
	@echo "セットアップ完了"

# Initialize
.PHONY: init
init:
	@echo "データベースと設定を初期化しています..."
	$(PYTHON) scripts/initialize.py
	@echo "初期化完了"

# Run development server
.PHONY: run
run:
	@echo "開発サーバーを起動しています..."
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Docker
.PHONY: docker-build
docker-build:
	@echo "Dockerイメージをビルドしています..."
	$(DOCKER_COMPOSE) build

.PHONY: docker-up
docker-up:
	@echo "Dockerコンテナを起動しています..."
	$(DOCKER_COMPOSE) up -d

.PHONY: docker-down
docker-down:
	@echo "Dockerコンテナを停止しています..."
	$(DOCKER_COMPOSE) down

.PHONY: docker-logs
docker-logs:
	@echo "Dockerコンテナのログを表示しています..."
	$(DOCKER_COMPOSE) logs -f

# Tests
.PHONY: test
test:
	@echo "テストを実行しています..."
	pytest

# Linting
.PHONY: lint
lint:
	@echo "コードを静的解析しています..."
	flake8 app/ scripts/ tests/
	isort --check-only app/ scripts/ tests/
	black --check app/ scripts/ tests/

# Formatting
.PHONY: format
format:
	@echo "コードをフォーマットしています..."
	isort app/ scripts/ tests/
	black app/ scripts/ tests/

# Clean
.PHONY: clean
clean:
	@echo "一時ファイルを削除しています..."
	rm -rf __pycache__
	rm -rf app/__pycache__
	rm -rf app/**/__pycache__
	rm -rf tests/__pycache__
	rm -rf tests/**/__pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".DS_Store" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	@echo "削除完了"

# Backup
.PHONY: backup
backup:
	@echo "バックアップを作成しています..."
	$(PYTHON) scripts/backup.py
	@echo "バックアップ完了"

# Documentation
.PHONY: docs
docs:
	@echo "ドキュメントを生成しています..."
	@mkdir -p docs/build
	@echo "ドキュメント生成完了"

# Production
.PHONY: prod-up
prod-up:
	@echo "本番環境でコンテナを起動しています..."
	ENV_FOR_DYNACONF=production $(DOCKER_COMPOSE) up -d

.PHONY: prod-deploy
prod-deploy:
	@echo "本番環境へデプロイしています..."
	bash scripts/deploy.sh -e production -b -u

# Cron setup
.PHONY: cron-setup
cron-setup:
	@echo "cronジョブをセットアップしています..."
	bash scripts/setup_cron.sh -i
	@echo "cronジョブのセットアップ完了"