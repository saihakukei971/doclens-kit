# app/services/archiver.py
import os
import shutil
import sqlite3
import zipfile
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import glob
import asyncio

from app.core.logger import log
from app.core.config import settings
from app.core.database import execute_query, execute_query_single, execute_update
from app.utils.file_utils import make_archive


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


async def create_archive_database(db_path: str):
    """
    Create and prepare a new archive database.

    Args:
        db_path: Path to database file
    """
    try:
        # Run in thread pool to avoid blocking
        await asyncio.to_thread(_create_archive_database_sync, db_path)

        log.info(f"アーカイブデータベース作成完了: {db_path}")

    except Exception as e:
        log.error(f"アーカイブデータベース作成エラー: {e}")
        raise


def _create_archive_database_sync(db_path: str):
    """
    Create and prepare a new archive database (synchronous version).

    Args:
        db_path: Path to database file
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Connect to SQLite database
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Create tables
    c.execute("""
    CREATE TABLE documents (
        id INTEGER PRIMARY KEY,
        title TEXT,
        doc_type TEXT,
        file_path TEXT,
        file_size INTEGER,
        mime_type TEXT,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        status TEXT,
        department TEXT,
        uploader TEXT
    )
    """)

    c.execute("""
    CREATE VIRTUAL TABLE document_content USING fts5(
        document_id,
        content,
        tokenize='trigram'
    )
    """)

    c.execute("""
    CREATE TABLE document_fields (
        id INTEGER PRIMARY KEY,
        document_id INTEGER,
        field_name TEXT,
        field_value TEXT,
        confidence REAL,
        FOREIGN KEY(document_id) REFERENCES documents(id)
    )
    """)

    c.execute("""
    CREATE TABLE document_relations (
        id INTEGER PRIMARY KEY,
        document_id INTEGER,
        related_document_id INTEGER,
        relation_type TEXT,
        FOREIGN KEY(document_id) REFERENCES documents(id),
        FOREIGN KEY(related_document_id) REFERENCES documents(id)
    )
    """)

    # Create indexes
    c.execute("CREATE INDEX idx_documents_doc_type ON documents(doc_type)")
    c.execute("CREATE INDEX idx_documents_created_at ON documents(created_at)")
    c.execute("CREATE INDEX idx_document_fields_document_id ON document_fields(document_id)")

    # Add archive metadata
    c.execute("""
    CREATE TABLE archive_metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Add creation timestamp
    c.execute(
        "INSERT INTO archive_metadata (key, value) VALUES (?, ?)",
        ("created_at", datetime.now().isoformat())
    )

    # Commit changes
    conn.commit()
    conn.close()


async def copy_data_to_archive(db_path: str, document_ids: List[int]):
    """
    Copy document data to archive database.

    Args:
        db_path: Path to archive database
        document_ids: List of document IDs to archive
    """
    try:
        # Run in thread pool to avoid blocking
        await asyncio.to_thread(_copy_data_to_archive_sync, db_path, document_ids)

        log.info(f"アーカイブへのデータコピー完了: {len(document_ids)}件")

    except Exception as e:
        log.error(f"アーカイブへのデータコピーエラー: {e}")
        raise


def _copy_data_to_archive_sync(db_path: str, document_ids: List[int]):
    """
    Copy document data to archive database (synchronous version).

    Args:
        db_path: Path to archive database
        document_ids: List of document IDs to archive
    """
    # Connect to source database (active database)
    source_db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    source_conn = sqlite3.connect(source_db_path)
    source_conn.row_factory = sqlite3.Row
    source_cursor = source_conn.cursor()

    # Connect to target database (archive)
    target_conn = sqlite3.connect(db_path)
    target_conn.row_factory = sqlite3.Row

    # Prepare placeholders for SQL query
    placeholders = ",".join(["?"] * len(document_ids))

    # Copy documents
    source_cursor.execute(
        f"""
        SELECT id, title, doc_type, file_path, file_size, mime_type,
               created_at, updated_at, status, department, uploader
        FROM documents
        WHERE id IN ({placeholders})
        """,
        document_ids
    )

    documents = source_cursor.fetchall()

    target_cursor = target_conn.cursor()
    for doc in documents:
        target_cursor.execute(
            """
            INSERT INTO documents (id, title, doc_type, file_path, file_size, mime_type,
                                   created_at, updated_at, status, department, uploader)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc["id"], doc["title"], doc["doc_type"], doc["file_path"], doc["file_size"],
                doc["mime_type"], doc["created_at"], doc["updated_at"], doc["status"],
                doc["department"], doc["uploader"]
            )
        )

    # Copy document content
    for doc_id in document_ids:
        source_cursor.execute(
            "SELECT document_id, content FROM document_content WHERE document_id = ?",
            (doc_id,)
        )
        content = source_cursor.fetchone()

        if content:
            target_cursor.execute(
                "INSERT INTO document_content (document_id, content) VALUES (?, ?)",
                (content["document_id"], content["content"])
            )

    # Copy document fields
    source_cursor.execute(
        f"""
        SELECT id, document_id, field_name, field_value, confidence
        FROM document_fields
        WHERE document_id IN ({placeholders})
        """,
        document_ids
    )

    fields = source_cursor.fetchall()

    for field in fields:
        target_cursor.execute(
            """
            INSERT INTO document_fields (id, document_id, field_name, field_value, confidence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (field["id"], field["document_id"], field["field_name"], field["field_value"], field["confidence"])
        )

    # Copy document relations
    source_cursor.execute(
        f"""
        SELECT id, document_id, related_document_id, relation_type
        FROM document_relations
        WHERE document_id IN ({placeholders})
        OR related_document_id IN ({placeholders})
        """,
        document_ids + document_ids
    )

    relations = source_cursor.fetchall()

    for relation in relations:
        # Only copy relations if both documents are being archived
        if relation["document_id"] in document_ids and relation["related_document_id"] in document_ids:
            target_cursor.execute(
                """
                INSERT INTO document_relations (id, document_id, related_document_id, relation_type)
                VALUES (?, ?, ?, ?)
                """,
                (relation["id"], relation["document_id"], relation["related_document_id"], relation["relation_type"])
            )

    # Add archive metadata
    target_cursor.execute(
        "INSERT INTO archive_metadata (key, value) VALUES (?, ?)",
        ("document_count", str(len(documents)))
    )

    # Commit changes
    target_conn.commit()

    # Close connections
    source_cursor.close()
    source_conn.close()
    target_cursor.close()
    target_conn.close()


async def copy_files_to_archive(archive_dir: str, document_files: List[Tuple[int, str]]):
    """
    Copy document files to archive directory.

    Args:
        archive_dir: Path to archive directory
        document_files: List of (document_id, file_path) tuples
    """
    try:
        # Create files directory in archive
        files_dir = os.path.join(archive_dir, "files")
        os.makedirs(files_dir, exist_ok=True)

        # Copy each file
        copied_count = 0

        for doc_id, file_path in document_files:
            source_path = os.path.join(settings.DOCUMENT_PATH, file_path)

            if not os.path.exists(source_path):
                log.warning(f"ファイルが見つかりません: {source_path}")
                continue

            # Create target directory
            target_dir = os.path.join(files_dir, os.path.dirname(file_path))
            os.makedirs(target_dir, exist_ok=True)

            # Copy file
            target_path = os.path.join(files_dir, file_path)
            await asyncio.to_thread(shutil.copy2, source_path, target_path)

            copied_count += 1

        log.info(f"アーカイブへのファイルコピー完了: {copied_count}/{len(document_files)}件")

    except Exception as e:
        log.error(f"アーカイブへのファイルコピーエラー: {e}")
        raise


async def clean_old_archives(keep_count: int = 12):
    """
    Clean old archives, keeping only the specified number of most recent ones.

    Args:
        keep_count: Number of most recent archives to keep
    """
    try:
        log.info(f"古いアーカイブのクリーンアップ開始 (保持数: {keep_count})")

        # Find all archive directories
        archive_dirs = []

        for item in os.listdir(settings.ARCHIVE_PATH):
            item_path = os.path.join(settings.ARCHIVE_PATH, item)

            # Check if it's a directory with the format YYYY-MM
            if os.path.isdir(item_path) and re.match(r'^\d{4}-\d{2}$', item):
                archive_dirs.append(item_path)

            # Check if it's a zip file with the format archive_YYYY-MM.zip
            elif os.path.isfile(item_path) and re.match(r'^archive_\d{4}-\d{2}\.zip$', item):
                archive_dirs.append(item_path)

        # Sort by name (which should sort by date if using the YYYY-MM format)
        archive_dirs.sort(reverse=True)

        # Keep the most recent ones
        to_keep = archive_dirs[:keep_count]
        to_delete = archive_dirs[keep_count:]

        # Delete old archives
        for archive_path in to_delete:
            if os.path.isdir(archive_path):
                await asyncio.to_thread(shutil.rmtree, archive_path)
            else:
                os.remove(archive_path)

            log.info(f"古いアーカイブを削除: {archive_path}")

        log.info(f"古いアーカイブのクリーンアップ完了: {len(to_delete)}件削除, {len(to_keep)}件保持")

    except Exception as e:
        log.error(f"古いアーカイブのクリーンアップエラー: {e}")


async def vacuum_database():
    """
    Run VACUUM on the database to optimize it.
    """
    try:
        log.info("データベース最適化開始 (VACUUM)")

        # Get database path
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")

        # Run VACUUM in a separate thread
        await asyncio.to_thread(_vacuum_database_sync, db_path)

        log.info("データベース最適化完了")

    except Exception as e:
        log.error(f"データベース最適化エラー: {e}")


def _vacuum_database_sync(db_path: str):
    """
    Run VACUUM on the database (synchronous version).

    Args:
        db_path: Path to database file
    """
    # Connect to database
    conn = sqlite3.connect(db_path)

    # Run VACUUM
    conn.execute("VACUUM")

    # Close connection
    conn.close()


async def purge_deleted_documents(days_old: int = 30):
    """
    Permanently delete documents marked as 'deleted' older than the specified days.

    Args:
        days_old: Delete documents older than this many days
    """
    try:
        log.info(f"削除済みドキュメントの完全削除開始 ({days_old}日以上経過)")

        # Calculate cutoff date
        cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()

        # Get documents to purge
        documents = await execute_query(
            """
            SELECT id, file_path
            FROM documents
            WHERE status = 'deleted'
            AND updated_at < ?
            """,
            (cutoff_date,)
        )

        if not documents:
            log.info("完全削除対象のドキュメントはありません")
            return

        log.info(f"完全削除対象: {len(documents)}件のドキュメント")

        # Delete each document
        for doc in documents:
            doc_id = doc["id"]
            file_path = doc["file_path"]

            # Delete file
            if file_path:
                full_path = os.path.join(settings.DOCUMENT_PATH, file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)

            # Delete from database
            await execute_update(
                """
                DELETE FROM document_fields WHERE document_id = ?
                """,
                (doc_id,)
            )

            await execute_update(
                """
                DELETE FROM document_content WHERE document_id = ?
                """,
                (doc_id,)
            )

            await execute_update(
                """
                DELETE FROM document_relations
                WHERE document_id = ? OR related_document_id = ?
                """,
                (doc_id, doc_id)
            )

            await execute_update(
                """
                DELETE FROM feedback WHERE document_id = ?
                """,
                (doc_id,)
            )

            await execute_update(
                """
                DELETE FROM documents WHERE id = ?
                """,
                (doc_id,)
            )

        log.info(f"削除済みドキュメントの完全削除完了: {len(documents)}件")

    except Exception as e:
        log.error(f"削除済みドキュメントの完全削除エラー: {e}")