# app/api/system.py
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional, Dict, Any
import os
import shutil
import sqlite3
import time
from datetime import datetime
import platform
import psutil

from app.core.logger import log
from app.core.config import settings
from app.core.security import verify_api_key
from app.core.database import execute_query, execute_query_single, execute_update
from app.services.archiver import create_archive, clean_old_archives, vacuum_database
from app.services.classifier import retrain_classifier

router = APIRouter()

@router.get("/status", dependencies=[Depends(verify_api_key)])
async def get_system_status():
    """
    Get system status and statistics.
    """
    try:
        # Get document count
        doc_count_result = await execute_query_single(
            """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active,
                COUNT(CASE WHEN status = 'archived' THEN 1 END) as archived,
                COUNT(CASE WHEN status = 'deleted' THEN 1 END) as deleted
            FROM documents
            """
        )

        # Get document type distribution
        doc_types_result = await execute_query(
            """
            SELECT doc_type, COUNT(*) as count
            FROM documents
            WHERE status = 'active' AND doc_type IS NOT NULL
            GROUP BY doc_type
            ORDER BY count DESC
            LIMIT 10
            """
        )

        doc_types = [
            {"type": result["doc_type"], "count": result["count"]}
            for result in doc_types_result
        ]

        # Get database size
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        # Get document storage size
        doc_storage_size = 0
        doc_file_count = 0
        for root, dirs, files in os.walk(settings.DOCUMENT_PATH):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    doc_storage_size += os.path.getsize(file_path)
                    doc_file_count += 1

        # Get archive storage size
        archive_storage_size = 0
        archive_file_count = 0
        for root, dirs, files in os.walk(settings.ARCHIVE_PATH):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    archive_storage_size += os.path.getsize(file_path)
                    archive_file_count += 1

        # Get system info
        system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_total": psutil.disk_usage('/').total,
            "disk_free": psutil.disk_usage('/').free,
        }

        # Get most recent documents
        recent_docs = await execute_query(
            """
            SELECT id, title, doc_type, created_at
            FROM documents
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 5
            """
        )

        recent_documents = [
            {
                "id": doc["id"],
                "title": doc["title"],
                "doc_type": doc["doc_type"],
                "created_at": datetime.fromisoformat(doc["created_at"]),
            }
            for doc in recent_docs
        ]

        # Get feedback status
        feedback_result = await execute_query_single(
            """
            SELECT COUNT(*) as total, COUNT(CASE WHEN applied = 1 THEN 1 END) as applied
            FROM feedback
            """
        )

        # Prepare response
        response = {
            "status": "running",
            "timestamp": datetime.now().isoformat(),
            "documents": {
                "total": doc_count_result["total"] if doc_count_result else 0,
                "active": doc_count_result["active"] if doc_count_result else 0,
                "archived": doc_count_result["archived"] if doc_count_result else 0,
                "deleted": doc_count_result["deleted"] if doc_count_result else 0,
                "types": doc_types,
                "recent": recent_documents,
            },
            "storage": {
                "database": {
                    "size": db_size,
                    "size_human": format_file_size(db_size),
                },
                "documents": {
                    "size": doc_storage_size,
                    "size_human": format_file_size(doc_storage_size),
                    "file_count": doc_file_count,
                },
                "archives": {
                    "size": archive_storage_size,
                    "size_human": format_file_size(archive_storage_size),
                    "file_count": archive_file_count,
                },
                "total": {
                    "size": db_size + doc_storage_size + archive_storage_size,
                    "size_human": format_file_size(db_size + doc_storage_size + archive_storage_size),
                },
            },
            "system": system_info,
            "feedback": {
                "total": feedback_result["total"] if feedback_result else 0,
                "applied": feedback_result["applied"] if feedback_result else 0,
                "pending": (feedback_result["total"] - feedback_result["applied"]) if feedback_result else 0,
            },
        }

        return response

    except Exception as e:
        log.error(f"システム状態取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"システム状態取得エラー: {str(e)}")

@router.post("/archive", dependencies=[Depends(verify_api_key)])
async def run_archive(
    background_tasks: BackgroundTasks,
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    """
    Run archive process for specified year and month.
    """
    try:
        # Set default to previous month if not specified
        if year is None or month is None:
            now = datetime.now()
            if now.month == 1:
                year = now.year - 1
                month = 12
            else:
                year = now.year
                month = now.month - 1

        # Validate year and month
        if not (1900 <= year <= 2100 and 1 <= month <= 12):
            raise HTTPException(status_code=400, detail="無効な年月です")

        # Run archive in background
        background_tasks.add_task(create_archive, year, month)

        return {
            "message": f"{year}年{month}月のアーカイブ処理を開始しました",
            "year": year,
            "month": month,
        }

    except Exception as e:
        log.error(f"アーカイブ処理開始エラー: {e}")
        raise HTTPException(status_code=500, detail=f"アーカイブ処理開始エラー: {str(e)}")

@router.post("/clean-archives", dependencies=[Depends(verify_api_key)])
async def clean_archives(
    background_tasks: BackgroundTasks,
    keep_count: int = 12,
):
    """
    Clean old archives, keeping only the specified number of most recent ones.
    """
    try:
        # Validate keep_count
        if keep_count < 1:
            raise HTTPException(status_code=400, detail="保持アーカイブ数は1以上である必要があります")

        # Run cleaning in background
        background_tasks.add_task(clean_old_archives, keep_count)

        return {
            "message": f"古いアーカイブのクリーンアップを開始しました（最新{keep_count}件を保持）",
            "keep_count": keep_count,
        }

    except Exception as e:
        log.error(f"アーカイブクリーンアップエラー: {e}")
        raise HTTPException(status_code=500, detail=f"アーカイブクリーンアップエラー: {str(e)}")

@router.post("/vacuum", dependencies=[Depends(verify_api_key)])
async def run_vacuum(
    background_tasks: BackgroundTasks,
):
    """
    Run VACUUM on the database to optimize it.
    """
    try:
        # Run vacuum in background
        background_tasks.add_task(vacuum_database)

        return {
            "message": "データベースの最適化を開始しました",
        }

    except Exception as e:
        log.error(f"データベース最適化エラー: {e}")
        raise HTTPException(status_code=500, detail=f"データベース最適化エラー: {str(e)}")

@router.post("/retrain", dependencies=[Depends(verify_api_key)])
async def run_retrain(
    background_tasks: BackgroundTasks,
    force: bool = False,
):
    """
    Retrain the classifier with feedback data.
    """
    try:
        # Check if enough feedback is available
        feedback_count_result = await execute_query_single(
            """
            SELECT COUNT(*) as count
            FROM feedback
            WHERE applied = 0
            """
        )

        feedback_count = feedback_count_result["count"] if feedback_count_result else 0

        if feedback_count < 20 and not force:
            return {
                "message": f"再学習に必要なフィードバックが不足しています（{feedback_count}/20）",
                "feedback_count": feedback_count,
                "required": 20,
            }

        # Run retraining in background
        background_tasks.add_task(retrain_classifier)

        return {
            "message": "分類器の再学習を開始しました",
            "feedback_count": feedback_count,
        }

    except Exception as e:
        log.error(f"分類器再学習エラー: {e}")
        raise HTTPException(status_code=500, detail=f"分類器再学習エラー: {str(e)}")

def format_file_size(size_bytes):
    """Format file size in bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"