# 業務データ統合ハブ (Business Data Integration Hub)

企業内の多様なデータソースから情報を一元的に収集・管理・検索できるシステムです。紙文書のスキャン取り込みから様々なシステムのデータ連携まで対応し、部署間のコミュニケーションとデータ共有を効率化します。

## 目次

- [主な機能](#主な機能)
- [技術スタック](#技術スタック)
- [システム要件](#システム要件)
- [ディレクトリ構造](#ディレクトリ構造)
- [インストール方法](#インストール方法)
- [設定](#設定)
- [使用方法](#使用方法)
- [主要コンポーネント詳細](#主要コンポーネント詳細)
- [運用管理](#運用管理)
- [開発ガイド](#開発ガイド)
- [拡張性](#拡張性)
- [トラブルシューティング](#トラブルシューティング)
- [ライセンス](#ライセンス)

## 主な機能

- **多様なデータ取込**: ドラッグ＆ドロップ、フォルダ監視、スキャナー連携によるデータ取込
- **自動文書分類**: 機械学習とルールベースのハイブリッドによる文書タイプ自動判別
- **データ抽出**: 日付、金額、取引先等の情報自動抽出
- **全文検索**: OCR処理されたデータを含む強力な検索機能
- **アーカイブ管理**: 月次アーカイブによるパフォーマンス最適化

## 技術スタック

- **バックエンド**: Python 3.10+ / FastAPI
- **データベース**: SQLite (初期) → PostgreSQL (拡張時)
- **フロントエンド**: Vue.js / HTML5 / CSS
- **OCR処理**: Tesseract (pytesseract)
- **文書分析**: scikit-learn / spaCy (日本語NLP)
- **デプロイ**: Docker / 既存Webサーバー連携

### SQLiteからPostgreSQLへの拡張について

本システムは初期段階ではSQLiteを使用しています。これは以下の理由によります：

- **セットアップの容易さ**: 外部データベースサーバーが不要
- **保守の簡素化**: バックアップがファイルコピーで完結
- **十分なパフォーマンス**: 中小規模の導入（数十万ドキュメント程度）であれば十分対応可能

ただし、以下のような場合はPostgreSQLへの移行を推奨します：

- 同時アクセスユーザーが20名を超える場合
- ドキュメント数が30万件を超える場合
- 複雑な検索クエリが頻繁に実行される場合

移行手順は[拡張性](#拡張性)セクションに記載しています。

## システム要件

- Windows Server 2016 以降（推奨）または Windows 10/11 Pro
- Python 3.10以上
- Tesseract OCR 5.0 以上（日本語モデル含む）
- Docker Desktop (Windows版) ※Docker使用の場合
- 最小ハードウェア要件:
  - CPU: 2コア以上
  - メモリ: 4GB以上（OCR処理時は一時的に高負荷）
  - ストレージ: 100GB以上を推奨

## ディレクトリ構造

```
/project_root/
├── app/                      # アプリケーションコード
│   ├── api/                  # APIエンドポイント
│   │   ├── __init__.py
│   │   ├── documents.py      # 文書関連API
│   │   ├── search.py         # 検索API
│   │   └── system.py         # システム管理API
│   ├── core/                 # コア機能
│   │   ├── __init__.py
│   │   ├── config.py         # 設定管理
│   │   ├── database.py       # DB接続管理
│   │   ├── logger.py         # ログ設定
│   │   └── security.py       # セキュリティ機能
│   ├── models/               # データモデル
│   │   ├── __init__.py
│   │   ├── document.py       # 文書モデル
│   │   └── search.py         # 検索モデル
│   ├── services/             # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── document_processor.py  # 文書処理
│   │   ├── ocr_service.py    # OCR処理
│   │   ├── classifier.py     # 文書分類
│   │   ├── search_service.py # 検索サービス
│   │   └── archiver.py       # アーカイブ処理
│   ├── utils/                # ユーティリティ
│   │   ├── __init__.py
│   │   ├── file_utils.py     # ファイル操作
│   │   └── text_utils.py     # テキスト処理
│   ├── web/                  # Webフロントエンド
│   │   ├── __init__.py
│   │   ├── static/           # 静的ファイル
│   │   │   ├── css/          # CSS
│   │   │   │   └── styles.css # スタイルシート
│   │   │   └── js/           # JavaScript
│   │   │       └── main.js   # メインJS
│   │   └── templates/        # テンプレート
│   │       └── index.html    # メインページ
│   ├── __init__.py
│   └── main.py               # アプリケーションエントリーポイント
├── config/                   # 設定ファイル
│   ├── default.toml          # 基本設定
│   └── classifier_config.yaml # 分類設定
├── data/                     # データストレージ
│   ├── documents/            # 文書保存
│   │   └── YYYY/MM/DD/       # 階層構造
│   └── archives/             # アーカイブ
├── logs/                     # ログファイル
├── models/                   # 機械学習モデル
├── backups/                  # バックアップ
├── scripts/                  # 運用スクリプト
│   ├── archive_task.py       # アーカイブバッチ
│   ├── backup.py             # バックアップ
│   ├── deploy.ps1            # デプロイスクリプト
│   ├── initialize.py         # 初期化スクリプト
│   ├── setup_scheduler.ps1   # タスクスケジューラ設定
│   └── vacuum_task.py        # DB最適化
├── docker-compose.yml        # Docker設定
├── Dockerfile                # Docker定義
├── Makefile                  # Make設定
├── .gitignore                # Git除外設定
├── requirements.txt          # 依存ライブラリ
└── README.md                 # プロジェクト説明
```

## インストール方法

### Dockerを使用する場合（推奨）

1. リポジトリをクローン
   ```bash
   git clone https://github.com/yourusername/business-data-hub.git
   cd business-data-hub
   ```

2. 初期化スクリプトを実行
   ```bash
   python scripts/initialize.py
   ```

3. Dockerコンテナをビルド・実行
   ```bash
   docker-compose up -d
   ```

4. ブラウザで http://localhost:8000 にアクセス

### 直接インストールする場合（Windows）

1. リポジトリをクローン
   ```powershell
   git clone https://github.com/yourusername/business-data-hub.git
   cd business-data-hub
   ```

2. 仮想環境を作成・有効化
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. 依存パッケージをインストール
   ```powershell
   pip install -r requirements.txt
   ```

4. Tesseract OCRをインストール
   - [Tesseractインストーラー](https://github.com/UB-Mannheim/tesseract/wiki)をダウンロードしてインストール
   - インストール時に日本語言語パックを選択
   - システム環境変数のPATHに Tesseract インストールディレクトリを追加

5. 初期化スクリプトを実行
   ```powershell
   python scripts/initialize.py
   ```

6. サーバーを起動
   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

7. タスクスケジューラの設定（オプション）
   ```powershell
   .\scripts\setup_scheduler.ps1
   ```

## 設定

`config/default.toml` ファイルを編集して設定をカスタマイズできます：

```toml
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
# TESSERACT_CMD = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"  # Windowsでは必要に応じて設定

# Web interface settings
WEB_ENABLED = true
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000

# Logging settings
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### 文書分類設定

`config/classifier_config.yaml` で文書分類ルールをカスタマイズできます：

```yaml
# Document type classification configuration

document_types:
  - name: invoice  # 請求書
    keywords: ['請求書', '御請求書', 'インボイス', '支払い', 'Invoice']
    patterns:
      - field: 'amount'
        regex: '合計.*?([0-9,]+)円'
      - field: 'invoice_date'
        regex: '(発行日|請求日)[：:]\s*(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2})'
      # その他のパターン...

  - name: quotation  # 見積書
    keywords: ['見積書', '御見積書', 'お見積り', 'Quotation', '見積金額']
    patterns:
      - field: 'amount'
        regex: '(見積金額|合計).*?([0-9,]+)円'
      # その他のパターン...

  # その他の文書タイプ...
```

## 使用方法

### API ドキュメント

サーバー起動後、http://localhost:8000/docs でSwagger UIベースのAPIドキュメントにアクセスできます。

### ドキュメントアップロード

```python
import requests

url = "http://localhost:8000/api/documents/"
files = {"file": open("invoice.pdf", "rb")}
data = {"title": "請求書", "department": "経理部"}

response = requests.post(url, files=files, data=data)
print(response.json())
```

### ドキュメント検索

```python
import requests

url = "http://localhost:8000/api/search/"
params = {
    "query_text": "請求書 ABC商事",
    "doc_type": "invoice",
    "page": 1,
    "per_page": 20
}

response = requests.post(url, json=params)
results = response.json()
for doc in results["results"]:
    print(f"{doc['title']} - {doc['doc_type']}")
```

### システム状態確認

```python
import requests

url = "http://localhost:8000/api/system/status"
response = requests.get(url)
status = response.json()
print(f"ステータス: {status['status']}")
print(f"ドキュメント数: {status['documents']['total']}")
print(f"ストレージ使用量: {status['storage']['total']['size_human']}")
```

## 主要コンポーネント詳細

### 1. ドキュメント処理 (`app/services/document_processor.py`)

```python
async def process_document(document_id: int, text_content: str, doc_type: str = None) -> List[Dict[str, Any]]:
    """
    Process a document to extract fields and metadata.
    
    Args:
        document_id: Document ID
        text_content: Document text content
        doc_type: Document type
    
    Returns:
        List of extracted fields
    """
    try:
        extracted_fields = []
        
        # If document type is provided, use type-specific extraction
        if doc_type:
            extracted_fields = await extract_fields_by_type(text_content, doc_type)
        
        # Store extracted fields in database
        if extracted_fields:
            # Prepare queries for transaction
            queries = []
            for field in extracted_fields:
                queries.append((
                    """
                    INSERT INTO document_fields (document_id, field_name, field_value, confidence)
                    VALUES (?, ?, ?, ?)
                    """,
                    (document_id, field["field_name"], field["field_value"], field["confidence"])
                ))
            
            # Execute transaction
            if queries:
                await execute_transaction(queries)
        
        return extracted_fields
        
    except Exception as e:
        log.error(f"ドキュメント処理エラー: {e}")
        return []
```

ドキュメント処理モジュールは、アップロードされたファイルからテキストを抽出し、文書タイプを判別、関連情報を抽出します。OCR処理が必要な場合は `ocr_service.py` と連携します。

### 2. OCR処理 (`app/services/ocr_service.py`)

```python
async def process_ocr(file_path: str, language: str = None) -> Optional[str]:
    """
    Process an image or PDF file with OCR.
    
    Args:
        file_path: Path to file
        language: OCR language code
    
    Returns:
        Extracted text or None if processing failed
    """
    if not os.path.exists(file_path):
        log.error(f"OCR処理対象ファイルが存在しません: {file_path}")
        return None
    
    try:
        # Determine file type by extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Set language
        if not language:
            language = settings.OCR_LANGUAGE if hasattr(settings, "OCR_LANGUAGE") else "jpn+eng"
        
        # Process based on file type
        if ext in ['.pdf']:
            return await process_pdf(file_path, language)
        elif ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif']:
            return await process_image(file_path, language)
        else:
            log.warning(f"未対応のファイル形式: {ext}")
            return None
            
    except Exception as e:
        log.error(f"OCR処理エラー: {e}")
        return None
```

OCRサービスは、Tesseractを使用して画像やPDFからテキストを抽出します。日本語と英語の両方に対応し、非同期処理でパフォーマンスを最適化しています。

### 3. 文書分類 (`app/services/classifier.py`)

```python
async def classify_document(text: str) -> Optional[Dict[str, Any]]:
    """
    Classify a document based on its text content.
    
    Args:
        text: Document text content
    
    Returns:
        Dictionary with classification results or None if classification failed
    """
    if not text:
        return None
    
    try:
        # Normalize text
        text = normalize_text(text)
        
        # Try rule-based classification first
        rule_result = await classify_by_rules(text)
        
        # If rule-based classification worked with high confidence, use it
        if rule_result and rule_result.get("confidence", 0) >= 0.8:
            return rule_result
        
        # Try ML-based classification if available
        ml_result = await classify_by_ml(text)
        
        # If ML classification worked with high confidence, use it
        if ml_result and ml_result.get("confidence", 0) >= 0.6:
            return ml_result
        
        # If both methods produced results, use the one with higher confidence
        if rule_result and ml_result:
            if rule_result.get("confidence", 0) >= ml_result.get("confidence", 0):
                return rule_result
            else:
                return ml_result
        
        # Return whichever result we have (or None if neither worked)
        return rule_result or ml_result
        
    except Exception as e:
        log.error(f"文書分類エラー: {e}")
        return None
```

分類エンジンは、ルールベースと機械学習の両方のアプローチを組み合わせています。ルールベースはYAML設定ファイルで定義された正規表現パターンとキーワードを使用し、ML分類はTF-IDFとRandomForestを使用して予測します。ユーザーフィードバックから学習して精度を向上させる機能も備えています。

### 4. 検索サービス (`app/services/search_service.py`)

```python
def build_search_query(search_query: SearchQuery) -> Tuple[str, List[Any], str]:
    """
    Build SQL query for document search.
    
    Args:
        search_query: Search query parameters
    
    Returns:
        Tuple of (WHERE clause, parameters, SELECT clause)
    """
    # Start with basic WHERE clause
    query = "WHERE 1=1"
    params = []
    
    # Add status filter
    if search_query.status:
        query += " AND d.status = ?"
        params.append(search_query.status)
    
    # Add document type filter
    if search_query.doc_type:
        query += " AND d.doc_type = ?"
        params.append(search_query.doc_type)
    
    # Add department filter
    if search_query.department:
        query += " AND d.department = ?"
        params.append(search_query.department)
    
    # Add uploader filter
    if search_query.uploader:
        query += " AND d.uploader = ?"
        params.append(search_query.uploader)
    
    # Add date range filters
    if search_query.date_from:
        date_from_str = search_query.date_from.isoformat() if isinstance(search_query.date_from, date) else search_query.date_from
        query += " AND d.created_at >= ?"
        params.append(date_from_str)
    
    if search_query.date_to:
        date_to_str = search_query.date_to.isoformat() if isinstance(search_query.date_to, date) else search_query.date_to
        # Add one day to include the entire end date
        query += " AND d.created_at <= ?"
        params.append(date_to_str + "T23:59:59")
    
    # Add full-text search if query provided
    select_clause = """
    SELECT d.id, d.title, d.doc_type, d.file_path, d.file_size, d.mime_type, 
           d.created_at, d.updated_at, d.status, d.department, d.uploader
    """
    
    if search_query.query_text and search_query.query_text.strip():
        # Clean and prepare search query
        query_text = normalize_text(search_query.query_text.strip())
        
        # Add full-text search condition
        query += """
        AND d.id IN (
            SELECT document_id 
            FROM document_content 
            WHERE document_content MATCH ?
        )
        """
        params.append(query_text)
        
        # Add relevance score to SELECT clause
        select_clause = """
        SELECT d.id, d.title, d.doc_type, d.file_path, d.file_size, d.mime_type, 
               d.created_at, d.updated_at, d.status, d.department, d.uploader,
               (SELECT rank FROM document_content WHERE document_id = d.id AND document_content MATCH ?) AS relevance
        """
        params.insert(0, query_text)  # Insert at beginning for SELECT
    
    return query, params, select_clause
```

検索サービスは、SQLiteのFTS5（全文検索）を使って日本語文書の検索を実現しています。メタデータフィルターと全文検索を組み合わせた複合検索、アーカイブを含む検索、関連文書の検索などの機能を提供します。

### 5. アーカイブ処理 (`app/services/archiver.py`)

```python
async def create_archive(year: int, month: int) -> Optional[str]:
    """
    Create an archive for the specified year and month.
    
    Args:
        year: Year
        month: Month
    
    Returns:
        Path to created archive or None if archiving failed
    """
    try:
        log.info(f"アーカイブ処理開始: {year}年{month}月")
        
        # Validate date
        if not (1900 <= year <= 2100 and 1 <= month <= 12):
            log.error(f"無効な年月: {year}/{month}")
            return None
        
        # Create archive directory
        archive_dir = os.path.join(settings.ARCHIVE_PATH, f"{year:04d}-{month:02d}")
        os.makedirs(archive_dir, exist_ok=True)
        
        # Create archive database file
        db_path = os.path.join(archive_dir, f"archive_{year:04d}-{month:02d}.db")
        
        # Get date range for the month
        start_date = f"{year:04d}-{month:02d}-01T00:00:00"
        
        # Calculate end date (first day of next month)
        if month == 12:
            end_date = f"{year+1:04d}-01-01T00:00:00"
        else:
            end_date = f"{year:04d}-{month+1:02d}-01T00:00:00"
        
        # Get documents for the month
        documents = await execute_query(
            """
            SELECT id, file_path
            FROM documents
            WHERE created_at >= ? AND created_at < ?
            AND status = 'active'
            """,
            (start_date, end_date)
        )
        
        if not documents:
            log.info(f"アーカイブ対象のドキュメントがありません: {year}/{month}")
            return None
        
        log.info(f"アーカイブ対象: {len(documents)}件のドキュメント")
        
        # Create and prepare archive database
        await create_archive_database(db_path)
        
        # Copy data to archive database
        document_ids = [doc["id"] for doc in documents]
        await copy_data_to_archive(db_path, document_ids)
        
        # Copy files to archive directory
        document_files = [(doc["id"], doc["file_path"]) for doc in documents]
        await copy_files_to_archive(archive_dir, document_files)
        
        # Update status in original database
        await execute_update(
            """
            UPDATE documents
            SET status = 'archived'
            WHERE id IN ({})
            """.format(",".join(["?"] * len(document_ids))),
            document_ids
        )
        
        # Create ZIP archive if configured
        if hasattr(settings, "ARCHIVE_ZIP") and settings.ARCHIVE_ZIP:
            zip_path = os.path.join(settings.ARCHIVE_PATH, f"archive_{year:04d}-{month:02d}.zip")
            await asyncio.to_thread(make_archive, archive_dir, zip_path)
            
            # If ZIP was successful and we're configured to remove original files
            if os.path.exists(zip_path) and hasattr(settings, "REMOVE_AFTER_ZIP") and settings.REMOVE_AFTER_ZIP:
                shutil.rmtree(archive_dir)
                return zip_path
        
        return archive_dir
        
    except Exception as e:
        log.error(f"アーカイブ作成エラー: {e}")
        return None
```

アーカイブサービスは、月次で古いデータを別のSQLiteデータベースにアーカイブし、オプションでNASなどの外部ストレージに移動することができます。システムのパフォーマンスを維持しながら大量のデータを管理します。

## 運用管理

### 定期タスク (Windows タスクスケジューラ)

以下の定期タスクを設定することをお勧めします：

```powershell
# タスクスケジューラの設定
.\scripts\setup_scheduler.ps1
```

このスクリプトは以下のタスクを設定します：

- 月次アーカイブ（毎月1日の午前1時）
- データベース最適化（毎週日曜の午前2時）
- バックアップ（毎日午前3時）
- 削除済みドキュメントの完全削除（毎週日曜の午前4時）

手動でタスクスケジューラを設定する場合は、以下のコマンドを実行するよう設定します：

```powershell
# アーカイブタスク
python -m scripts.archive_task

# データベース最適化
python -m scripts.vacuum_task

# バックアップ
python -m scripts.backup
```

### バックアップ

手動バックアップの実行：

```powershell
python scripts/backup.py
```

バックアップは `backups/` ディレクトリに保存され、7日間保持されます。

### デプロイ

本番環境へのデプロイ：

```powershell
.\scripts\deploy.ps1 -Environment Production -Build -Start
```

### モニタリング

システム状態は API または Web インターフェースから確認できます：

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/system/status"
```

ログは `logs/` ディレクトリに保存され、日単位でローテーションされます。

## 拡張性

### 1. データベースの拡張 (SQLite → PostgreSQL)

SQLiteからPostgreSQLへの移行手順：

1. PostgreSQLをインストール（Windows用）
   - [PostgreSQLインストーラー](https://www.postgresql.org/download/windows/)からダウンロード
   - デフォルト設定でインストール

2. データベースの作成
   ```powershell
   psql -U postgres -c "CREATE DATABASE datahub;"
   psql -U postgres -c "CREATE USER datahub_user WITH PASSWORD 'your_password';"
   psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE datahub TO datahub_user;"
   ```

3. config/default.toml の DATABASE_URL を変更
   ```toml
   DATABASE_URL = "postgresql://datahub_user:your_password@localhost/datahub"
   ```

4. 必要なパッケージをインストール
   ```powershell
   pip install psycopg2-binary
   ```

5. マイグレーションスクリプトを作成（scripts/migrate_to_postgres.py）

6. マイグレーションを実行
   ```powershell
   python scripts/migrate_to_postgres.py
   ```

PostgreSQLの利点：
- 同時アクセス性能の向上
- より高度なインデックスと検索機能
- 大規模データセットでの優れたパフォーマンス
- バックアップと復元の柔軟性

### 2. OCR処理の拡張

より高度なOCRエンジンに置き換えるには：

1. 新しいOCRライブラリをインストール
   ```powershell
   pip install azure-ai-formrecognizer  # Azureの例
   ```

2. OCRサービスを拡張
   ```python
   # app/services/ocr_service.py に追加
   
   async def process_with_azure(file_path: str, language: str = None) -> Optional[str]:
       """
       Process document with Azure Form Recognizer.
       """
       # Azure Form Recognizerの実装
       pass
   ```

3. 設定ファイルに追加
   ```toml
   # config/default.toml に追加
   [ocr]
   engine = "azure"  # "tesseract" or "azure"
   azure_endpoint = "https://your-endpoint.cognitiveservices.azure.com/"
   azure_key = "your-api-key"
   ```

### 3. 文書分類の強化

より高度な分類モデルを導入するには：

1. 必要なライブラリをインストール
   ```powershell
   pip install transformers
   ```

2. BERTなどの深層学習モデルを導入
   ```python
   # app/services/classifier.py に追加
   
   async def classify_by_bert(text: str) -> Optional[Dict[str, Any]]:
       """
       Classify document using BERT model.
       """
       # BERTモデルの実装
       pass
   ```

## ユーザーガイド

### 基本的な使い方

#### ドキュメントのアップロード

1. ホーム画面から「アップロード」ボタンをクリック
2. ファイルをドラッグ＆ドロップするか、「ファイルを選択」をクリック
3. 必要に応じてタイトルや部署などのメタデータを入力
4. 「アップロード」ボタンをクリック
5. アップロード完了後、自動的に文書タイプが判別されます

#### 文書の検索

1. 検索ボックスにキーワードを入力
2. 必要に応じて文書タイプ、日付範囲などのフィルターを設定
3. 「検索」ボタンをクリック
4. 検索結果から目的の文書をクリック

#### 効果的な検索のコツ

1. **キーワードは具体的に**: 「請求書」よりも「ABC商事 請求書」のように具体的に
2. **フィルターを活用**: 文書タイプや日付範囲を指定して検索範囲を絞る
3. **AND検索を使う**: スペースで区切ることで複数のキーワードをAND検索できます（例：「ABC商事 2023年4月」）

### 特別なニーズに対応した使用方法

#### 検索の絞り込み方法（広範囲の検索を避けるために）

1. **段階的に検索**: まず主要キーワードで検索し、結果が多すぎる場合は条件を追加
2. **日付範囲の活用**: 必ず日付範囲を指定して検索対象期間を限定
3. **部署フィルター**: 自分の部署のドキュメントに絞り込む
4. **文書タイプの指定**: 「すべての文書」ではなく特定の文書タイプを選択

#### 緊急時の対応方法

緊急で特定の文書（例：特定顧客の最近の請求書）が必要な場合：

1. **顧客名で検索**: まず顧客名のみで検索
2. **文書タイプをフィルター**: 「請求書」に絞り込む
3. **最新のもの順に表示**: 並び順を「最新のもの順」に設定
4. **日付範囲を設定**: 過去1〜3ヶ月程度に絞る

これらの手順を踏むことで、システムに負荷をかけずに素早く目的の文書を見つけることができます。

#### 大量のデータを検索する場合

大量のデータを一度に検索すると、システムに負荷がかかり応答が遅くなる可能性があります。以下の方法で効率的に検索してください：

1. **検索を分割**: 一度に全期間ではなく、四半期や年度ごとに分けて検索
2. **エクスポート機能の活用**: 検索結果をCSVでエクスポートし、Excelで詳細分析
3. **アーカイブ検索を避ける**: 通常の検索で十分な場合は「アーカイブを含む」のチェックを外す
4. **管理者に相談**: 特殊な検索条件が必要な場合は管理者に相談

### トラブルシューティング（ユーザー向け）

#### 検索結果が表示されない

1. **スペルミス**: キーワードのスペルや表記を確認（例：全角/半角、ひらがな/カタカナ）
2. **検索条件の緩和**: 検索条件が厳しすぎないか確認し、一部の条件を外してみる
3. **日付範囲の確認**: 正しい期間を指定しているか確認
4. **アーカイブを含む**: 古いデータを検索する場合は「アーカイブを含む」をチェック

#### アップロードに失敗する

1. **ファイルサイズ**: 2GB以上のファイルはアップロードできません
2. **ファイル形式**: サポートされていないファイル形式でないか確認
3. **ネットワーク接続**: ネットワーク接続を確認
4. **ブラウザの更新**: ブラウザをリロードしてから再試行

#### OCR結果が不正確

1. **画像の品質**: スキャン品質を向上させる（解像度を上げる、傾きを修正する）
2. **手書き文字の限界**: 手書き文字は認識精度が低下します
3. **修正機能**: OCR結果を手動で修正することも可能です

## エンジニア向け管理ガイド

### 日常的な管理タスク

#### システム監視

1. ログの確認
   ```powershell
   Get-Content -Path "logs\app_$(Get-Date -Format 'yyyy-MM-dd').log" -Tail 100
   ```

2. システム状態の確認
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/api/system/status"
   ```

3. ディスク使用量の確認
   ```powershell
   Get-ChildItem -Path "data" -Recurse | Measure-Object -Property Length -Sum
   ```

#### 定期メンテナンス

1. データベース最適化の手動実行
   ```powershell
   python -m scripts.vacuum_task
   ```

2. 手動バックアップの実行
   ```powershell
   python -m scripts.backup
   ```

3. 古いログの削除
   ```powershell
   Get-ChildItem -Path "logs" -Filter "*.log" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item
   ```

### 緊急対応（エンジニア向け）

#### 特殊条件での検索

Webインターフェースで対応できない複雑な検索条件の場合、SQLクエリを直接実行できます：

1. SQLiteデータベースに接続
   ```powershell
   sqlite3 data\documents.db
   ```

2. 特殊な条件での検索例（特定ユーザーの最近1週間の請求書）
   ```sql
   SELECT d.id, d.title, d.created_at, d.file_path 
   FROM documents d 
   WHERE d.doc_type = 'invoice' 
   AND d.uploader = 'username' 
   AND d.created_at > datetime('now', '-7 days') 
   ORDER BY d.created_at DESC;
   ```

3. 検索結果のCSV出力
   ```sql
   .mode csv
   .output results.csv
   SELECT d.id, d.title, d.created_at, d.file_path, df.field_value as amount
   FROM documents d 
   JOIN document_fields df ON d.id = df.document_id
   WHERE d.doc_type = 'invoice' 
   AND df.field_name = 'amount'
   AND d.created_at > datetime('now', '-7 days');
   .output stdout
   ```

#### システムパフォーマンスの緊急改善

1. 不要なインデックスの削除（検索エンジン負荷軽減）
   ```sql
   DELETE FROM document_content WHERE document_id IN (
     SELECT document_id FROM documents 
     WHERE created_at < datetime('now', '-2 years')
   );
   ```

2. 一時的に検索制限を緩和（設定ファイル変更）
   ```powershell
   # config/default.toml に以下を追加
   [search]
   max_query_length = 100  # 長いクエリを許可
   timeout = 60  # タイムアウトを延長（秒）
   ```

3. サーバーのメモリ割り当てを増加
   ```powershell
   $Env:UVICORN_WORKERS = 4  # ワーカー数を増加
   $Env:UVICORN_LIMIT_MAX_REQUESTS = 1000  # 最大リクエスト数を制限
   ```

#### データベース直接操作（緊急時のみ）

1. 壊れたレコードの修復
   ```sql
   UPDATE documents SET status = 'active' WHERE status IS NULL;
   UPDATE documents SET doc_type = 'unknown' WHERE doc_type IS NULL;
   ```

2. 重複レコードの削除
   ```sql
   DELETE FROM documents 
   WHERE id IN (
     SELECT d1.id FROM documents d1
     JOIN (
       SELECT file_path, MIN(id) as min_id
       FROM documents
       GROUP BY file_path
       HAVING COUNT(*) > 1
     ) d2 ON d1.file_path = d2.file_path
     WHERE d1.id > d2.min_id
   );
   ```

3. インデックスの再構築
   ```sql
   INSERT INTO document_content(document_content) VALUES('optimize');
   VACUUM;
   ```

#### システム復旧手順

1. バックアップからの復元
   ```powershell
   # サービス停止
   docker-compose down  # Docker使用時
   
   # 最新バックアップの特定
   $latest_backup = Get-ChildItem -Path "backups" -Filter "backup_*.tar.gz" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
   
   # バックアップから復元
   python scripts/restore.py $latest_backup.FullName
   
   # サービス再開
   docker-compose up -d  # Docker使用時
   ```

2. データベース再構築（最終手段）
   ```powershell
   # 既存データベースのバックアップ
   Copy-Item -Path "data\documents.db" -Destination "data\documents.db.bak"
   
   # データベース再作成
   Remove-Item -Path "data\documents.db"
   python scripts/initialize.py -f
   ```

### 改修・カスタマイズガイド

#### 新しい文書タイプの追加

1. classifier_config.yaml に新しい文書タイプを追加
   ```yaml
   # config/classifier_config.yaml に追加
   - name: contract  # 契約書
     keywords: ['契約書', '覚書', '合意書', 'Contract', 'Agreement']
     patterns:
       - field: 'contract_date'
         regex: '(契約日|締結日)[：:]\s*(\d{4}[年/\-]\d{1,2}[月/\-]\d{1,2})'
       - field: 'contract_period'
         regex: '(契約期間|有効期間)[：:]\s*([^\n\r]{5,50})'
   ```

2. フロントエンドに新しい文書タイプを追加
   ```html
   <!-- app/web/templates/index.html を修正 -->
   <select id="doc_type" name="doc_type">
     <option value="">すべての文書タイプ</option>
     <option value="invoice">請求書</option>
     <option value="quotation">見積書</option>
     <option value="contract">契約書</option> <!-- 追加 -->
   </select>
   ```

#### カスタムフィールド抽出の追加

1. 新しい抽出パターンを追加
   ```yaml
   # config/classifier_config.yaml の該当する文書タイプに追加
   - field: 'tax_id'
     regex: '(税務署ID|納税者番号)[：:]\s*([A-Z0-9\-]{10,15})'
   ```

2. 抽出処理をカスタマイズ
   ```python
   # app/services/document_processor.py に追加
   
   async def extract_tax_id(text: str) -> Optional[str]:
       """Extract tax ID from text."""
       patterns = [
           r'税務署ID[：:]\s*([A-Z0-9\-]{10,15})',
           r'納税者番号[：:]\s*([A-Z0-9\-]{10,15})',
           r'Tax ID[：:]\s*([A-Z0-9\-]{10,15})'
       ]
       
       for pattern in patterns:
           match = re.search(pattern, text)
           if match:
               return match.group(1)
       
       return None
   ```

#### パフォーマンスチューニング

1. データベースインデックスの最適化
   ```sql
   CREATE INDEX IF NOT EXISTS idx_documents_created_uploader ON documents(created_at, uploader);
   CREATE INDEX IF NOT EXISTS idx_document_fields_value ON document_fields(field_name, field_value);
   ```

2. キャッシュの導入
   ```python
   # app/services/search_service.py に追加
   
   # キャッシュ用辞書
   _search_cache = {}
   _cache_timeout = 300  # 5分
   
   async def search_with_cache(search_query: SearchQuery) -> Dict[str, Any]:
       """Search with cache."""
       cache_key = f"{search_query.query_text}:{search_query.doc_type}:{search_query.page}"
       
       # キャッシュ確認
       if cache_key in _search_cache:
           cache_entry = _search_cache[cache_key]
           if time.time() - cache_entry["timestamp"] < _cache_timeout:
               return cache_entry["result"]
       
       # 通常の検索実行
       result = await search_documents(search_query)
       
       # キャッシュに保存
       _search_cache[cache_key] = {
           "timestamp": time.time(),
           "result": result
       }
       
       return result
   ```

#### サードパーティサービス連携

1. 電子署名サービス（DocuSign等）との連携
   ```python
   # app/services/integration.py を新規作成
   
   async def send_for_signature(document_id: int, recipient_email: str) -> str:
       """Send document for electronic signature."""
       # ドキュメント情報を取得
       document = await get_document(document_id)
       
       # DocuSign APIを呼び出し
       # （実装は省略）
       
       return signature_request_id
   ```

2. チャットボット連携
   ```python
   # app/api/integrations.py を新規作成
   
   @router.post("/chatbot/query")
   async def chatbot_query(query: str = Body(..., embed=True)):
       """Handle chatbot query about documents."""
       # 質問内容から検索クエリを生成
       search_query = generate_search_query_from_natural_language(query)
       
       # 検索実行
       results = await search_documents(search_query)
       
       # 結果からチャットボット用の応答を生成
       response = generate_chatbot_response(query, results)
       
       return {"response": response, "sources": [r.id for r in results]}
   ```

## トラブルシューティング

### よくある問題と解決策

| 問題 | 考えられる原因 | 解決策 |
|------|--------------|-------|
| アップロードが失敗する | ファイルサイズが大きすぎる | config/default.toml の UPLOAD_SIZE_LIMIT を確認 |
| OCR処理が動作しない | Tesseractがインストールされていない | Tesseractと言語パックをインストール |
| 検索結果が表示されない | FTS5が有効になっていない | SQLiteをリビルドまたはテーブルを再作成 |
| アーカイブが失敗する | ディスク容量不足 | ディスク使用量を確認・クリーンアップ |
| システムが遅い | 多量のデータ | データベース最適化を実行：`python scripts/vacuum_task.py` |
| Windows環境での文字化け | コードページの問題 | `chcp 65001` を実行してUTF-8に設定 |

### ログの確認

問題の診断には、まずログを確認してください：

```powershell
# ログファイルの確認
Get-Content -Path "logs\app_$(Get-Date -Format 'yyyy-MM-dd').log" -Tail 100

# Docker内のログ確認
docker-compose logs -f
```

### データベースのバックアップと復元

```powershell
# バックアップの作成
python scripts/backup.py

# バックアップから復元
python scripts/restore.py backups/backup_20230101_120000.tar.gz
```

### 環境のリセット

問題が解決しない場合は、環境を完全にリセットできます：

```powershell
# Dockerコンテナを停止・削除
docker-compose down -v

# データを削除（注意: すべてのデータが失われます）
Remove-Item -Path "data\*" -Recurse -Force
Remove-Item -Path "logs\*" -Recurse -Force
Remove-Item -Path "models\*" -Recurse -Force

# 再初期化
python scripts/initialize.py -f

# コンテナを再起動
docker-compose up -d
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細については [LICENSE](LICENSE) ファイルを参照してください。

## 作者

あなたの名前

---

これは業務データ統合ハブのプロジェクトです。詳細な情報や質問がある場合は、Issueを作成するか、[your-email@example.com](mailto:your-email@example.com) にお問い合わせください。
