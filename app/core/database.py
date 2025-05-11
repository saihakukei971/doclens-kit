# app/core/database.py
import aiosqlite
import sqlite3
import os
from pathlib import Path
from app.core.config import settings
from app.core.logger import log

# Ensure database directory exists
def _ensure_db_path():
    """Ensure database directory exists."""
    db_path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    os.makedirs(db_path.parent, exist_ok=True)
    return str(db_path)

# Database connection
_connection = None

# Initialize database
async def init_db():
    """Initialize the database connection and tables."""
    global _connection

    db_path = _ensure_db_path()
    log.info(f"データベース初期化: {db_path}")

    # Connect to database
    _connection = await aiosqlite.connect(db_path)
    _connection.row_factory = aiosqlite.Row

    # Enable foreign keys
    await _connection.execute("PRAGMA foreign_keys = ON")

    # Create tables
    await _create_tables()

    log.info("データベース初期化完了")
    return _connection

# Close database connection
async def close_db():
    """Close the database connection."""
    global _connection
    if _connection:
        await _connection.close()
        _connection = None
        log.info("データベース接続終了")

# Get database connection
async def get_db():
    """Get database connection."""
    global _connection
    if not _connection:
        await init_db()
    return _connection

# Create database tables
async def _create_tables():
    """Create database tables if they don't exist."""
    global _connection

    # Documents table
    await _connection.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY,
        title TEXT,               -- 文書タイトル
        doc_type TEXT,            -- 文書タイプ (invoice, quotation, etc.)
        file_path TEXT,           -- ファイルパス
        file_size INTEGER,        -- ファイルサイズ
        mime_type TEXT,           -- MIMEタイプ
        created_at TIMESTAMP,     -- 作成日時
        updated_at TIMESTAMP,     -- 更新日時
        status TEXT,              -- ステータス (active, archived)
        department TEXT,          -- 部署
        uploader TEXT             -- アップロードユーザー
    )
    """)

    # Document content table (FTS5)
    await _connection.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS document_content USING fts5(
        document_id,
        content,
        tokenize='trigram'        -- 日本語対応
    )
    """)

    # Document fields table
    await _connection.execute("""
    CREATE TABLE IF NOT EXISTS document_fields (
        id INTEGER PRIMARY KEY,
        document_id INTEGER,
        field_name TEXT,          -- フィールド名 (amount, date, etc.)
        field_value TEXT,         -- 値
        confidence REAL,          -- 信頼度
        FOREIGN KEY(document_id) REFERENCES documents(id)
    )
    """)

    # Document relations table
    await _connection.execute("""
    CREATE TABLE IF NOT EXISTS document_relations (
        id INTEGER PRIMARY KEY,
        document_id INTEGER,
        related_document_id INTEGER,
        relation_type TEXT,       -- 関連タイプ
        FOREIGN KEY(document_id) REFERENCES documents(id),
        FOREIGN KEY(related_document_id) REFERENCES documents(id)
    )
    """)

    # Feedback table for ML improvement
    await _connection.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY,
        document_id INTEGER,
        original_classification TEXT,
        corrected_classification TEXT,
        feedback_date TIMESTAMP,
        applied BOOLEAN DEFAULT FALSE,
        FOREIGN KEY(document_id) REFERENCES documents(id)
    )
    """)

    # Create indexes
    await _connection.execute("CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type)")
    await _connection.execute("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
    await _connection.execute("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at)")
    await _connection.execute("CREATE INDEX IF NOT EXISTS idx_document_fields_document_id ON document_fields(document_id)")

    # Commit changes
    await _connection.commit()

    log.info("データベーステーブル作成完了")

# Execute query and return results
async def execute_query(query, params=None):
    """Execute a database query and return results."""
    db = await get_db()
    try:
        if params:
            cursor = await db.execute(query, params)
        else:
            cursor = await db.execute(query)

        return await cursor.fetchall()
    except Exception as e:
        log.error(f"クエリ実行エラー: {e}")
        return []

# Execute query and return a single result
async def execute_query_single(query, params=None):
    """Execute a database query and return a single result."""
    db = await get_db()
    try:
        if params:
            cursor = await db.execute(query, params)
        else:
            cursor = await db.execute(query)

        return await cursor.fetchone()
    except Exception as e:
        log.error(f"クエリ実行エラー (single): {e}")
        return None

# Execute insert query and return the last inserted ID
async def execute_insert(query, params=None):
    """Execute an insert query and return the last inserted ID."""
    db = await get_db()
    try:
        if params:
            cursor = await db.execute(query, params)
        else:
            cursor = await db.execute(query)

        await db.commit()
        return cursor.lastrowid
    except Exception as e:
        log.error(f"挿入クエリ実行エラー: {e}")
        return None

# Execute update/delete query
async def execute_update(query, params=None):
    """Execute an update/delete query."""
    db = await get_db()
    try:
        if params:
            await db.execute(query, params)
        else:
            await db.execute(query)

        await db.commit()
        return True
    except Exception as e:
        log.error(f"更新クエリ実行エラー: {e}")
        return False

# Execute multiple queries in a transaction
async def execute_transaction(queries_and_params):
    """Execute multiple queries in a transaction."""
    db = await get_db()
    try:
        await db.execute("BEGIN TRANSACTION")

        for query, params in queries_and_params:
            if params:
                await db.execute(query, params)
            else:
                await db.execute(query)

        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        log.error(f"トランザクション実行エラー: {e}")
        return False