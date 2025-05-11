# app/api/documents.py
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query, Path
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
import os
import shutil
from datetime import datetime
import mimetypes
from pathlib import Path as FilePath

from app.core.logger import log
from app.core.config import settings
from app.core.security import verify_api_key
from app.core.database import execute_query, execute_query_single, execute_insert, execute_update, execute_transaction
from app.models.document import DocumentCreate, DocumentUpdate, DocumentResponse, DocumentListResponse, DocumentField, Feedback, FeedbackCreate, FeedbackResponse
from app.services.document_processor import process_document, save_uploaded_file, extract_text
from app.services.classifier import classify_document

router = APIRouter()

@router.post("/", response_model=DocumentResponse, dependencies=[Depends(verify_api_key)])
async def create_document(
    title: str = Form(...),
    doc_type: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    file: UploadFile = File(...),
    uploader: Optional[str] = Form(None),
):
    """
    Upload a new document.
    """
    try:
        # Check file size
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > settings.UPLOAD_SIZE_LIMIT:
            raise HTTPException(status_code=413, detail="ファイルサイズが制限を超えています")

        # Save the file
        date_path = datetime.now().strftime("%Y/%m/%d")
        rel_path = f"{date_path}/{file.filename}"
        full_path = await save_uploaded_file(file, rel_path)

        # Create document in DB
        mime_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"

        # Process document
        doc_data = DocumentCreate(
            title=title,
            doc_type=doc_type,
            department=department,
            file_path=rel_path,
            file_size=file_size,
            mime_type=mime_type,
            uploader=uploader,
        )

        # Extract text and classify if needed
        text_content = await extract_text(full_path, mime_type)

        if not doc_type and text_content:
            # Auto-classify document
            classification_result = await classify_document(text_content)
            if classification_result:
                doc_data.doc_type = classification_result["doc_type"]

        # Insert into database
        now = datetime.now().isoformat()
        doc_id = await execute_insert(
            """
            INSERT INTO documents
            (title, doc_type, file_path, file_size, mime_type, created_at, updated_at, status, department, uploader)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_data.title,
                doc_data.doc_type,
                doc_data.file_path,
                doc_data.file_size,
                doc_data.mime_type,
                now,
                now,
                "active",
                doc_data.department,
                doc_data.uploader
            )
        )

        if not doc_id:
            raise HTTPException(status_code=500, detail="ドキュメント登録に失敗しました")

        # Save text content to FTS table if available
        if text_content:
            await execute_insert(
                "INSERT INTO document_content (document_id, content) VALUES (?, ?)",
                (doc_id, text_content)
            )

            # Process document to extract fields
            field_data = await process_document(doc_id, text_content, doc_data.doc_type)

        # Return the created document
        result = await execute_query_single(
            """
            SELECT id, title, doc_type, file_path, file_size, mime_type,
                   created_at, updated_at, status, department, uploader
            FROM documents
            WHERE id = ?
            """,
            (doc_id,)
        )

        if not result:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")

        # Convert to response model
        response = {
            "id": result["id"],
            "title": result["title"],
            "doc_type": result["doc_type"],
            "file_size": result["file_size"],
            "mime_type": result["mime_type"],
            "created_at": datetime.fromisoformat(result["created_at"]),
            "updated_at": datetime.fromisoformat(result["updated_at"]),
            "department": result["department"],
            "status": result["status"],
            "uploader": result["uploader"],
        }

        # Get fields if any
        fields = await execute_query(
            """
            SELECT field_name, field_value, confidence
            FROM document_fields
            WHERE document_id = ?
            """,
            (doc_id,)
        )

        if fields:
            response["fields"] = [
                {
                    "field_name": field["field_name"],
                    "field_value": field["field_value"],
                    "confidence": field["confidence"]
                }
                for field in fields
            ]

        return response

    except Exception as e:
        log.error(f"ドキュメント作成エラー: {e}")
        raise HTTPException(status_code=500, detail=f"ドキュメント作成エラー: {str(e)}")

@router.get("/", response_model=DocumentListResponse, dependencies=[Depends(verify_api_key)])
async def list_documents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query("active"),
    doc_type: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
):
    """
    List documents with optional filtering.
    """
    try:
        # Build query
        query = """
        SELECT id, title, doc_type, file_path, file_size, mime_type,
               created_at, updated_at, status, department, uploader
        FROM documents
        WHERE 1=1
        """
        params = []

        # Add filters
        if status:
            query += " AND status = ?"
            params.append(status)

        if doc_type:
            query += " AND doc_type = ?"
            params.append(doc_type)

        if department:
            query += " AND department = ?"
            params.append(department)

        # Count total
        count_query = f"""
        SELECT COUNT(*) as total
        FROM documents
        WHERE 1=1
        """

        # Add filters to count query
        if status:
            count_query += " AND status = ?"

        if doc_type:
            count_query += " AND doc_type = ?"

        if department:
            count_query += " AND department = ?"

        # Get count
        count_result = await execute_query_single(count_query, params)
        total = count_result["total"] if count_result else 0

        # Add pagination
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.append(per_page)
        params.append((page - 1) * per_page)

        # Execute query
        results = await execute_query(query, params)

        # Prepare response
        items = []
        for result in results:
            item = {
                "id": result["id"],
                "title": result["title"],
                "doc_type": result["doc_type"],
                "file_size": result["file_size"],
                "mime_type": result["mime_type"],
                "created_at": datetime.fromisoformat(result["created_at"]),
                "updated_at": datetime.fromisoformat(result["updated_at"]),
                "department": result["department"],
                "status": result["status"],
                "uploader": result["uploader"],
            }
            items.append(item)

        return {
            "total": total,
            "items": items
        }

    except Exception as e:
        log.error(f"ドキュメント一覧取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"ドキュメント一覧取得エラー: {str(e)}")

@router.get("/{doc_id}", response_model=DocumentResponse, dependencies=[Depends(verify_api_key)])
async def get_document(
    doc_id: int = Path(..., gt=0),
):
    """
    Get a specific document by ID.
    """
    try:
        # Get document
        result = await execute_query_single(
            """
            SELECT id, title, doc_type, file_path, file_size, mime_type,
                   created_at, updated_at, status, department, uploader
            FROM documents
            WHERE id = ?
            """,
            (doc_id,)
        )

        if not result:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")

        # Convert to response model
        response = {
            "id": result["id"],
            "title": result["title"],
            "doc_type": result["doc_type"],
            "file_size": result["file_size"],
            "mime_type": result["mime_type"],
            "created_at": datetime.fromisoformat(result["created_at"]),
            "updated_at": datetime.fromisoformat(result["updated_at"]),
            "department": result["department"],
            "status": result["status"],
            "uploader": result["uploader"],
        }

        # Get fields if any
        fields = await execute_query(
            """
            SELECT field_name, field_value, confidence
            FROM document_fields
            WHERE document_id = ?
            """,
            (doc_id,)
        )

        if fields:
            response["fields"] = [
                {
                    "field_name": field["field_name"],
                    "field_value": field["field_value"],
                    "confidence": field["confidence"]
                }
                for field in fields
            ]

        return response

    except Exception as e:
        log.error(f"ドキュメント取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"ドキュメント取得エラー: {str(e)}")

@router.get("/{doc_id}/content", dependencies=[Depends(verify_api_key)])
async def get_document_content(
    doc_id: int = Path(..., gt=0),
):
    """
    Get the text content of a document.
    """
    try:
        # Get document content
        result = await execute_query_single(
            """
            SELECT content
            FROM document_content
            WHERE document_id = ?
            """,
            (doc_id,)
        )

        if not result:
            raise HTTPException(status_code=404, detail="ドキュメントコンテンツが見つかりません")

        return {"content": result["content"]}

    except Exception as e:
        log.error(f"ドキュメントコンテンツ取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"ドキュメントコンテンツ取得エラー: {str(e)}")

@router.get("/{doc_id}/file", dependencies=[Depends(verify_api_key)])
async def get_document_file(
    doc_id: int = Path(..., gt=0),
):
    """
    Download the original document file.
    """
    try:
        # Get document path
        result = await execute_query_single(
            """
            SELECT file_path, mime_type, title
            FROM documents
            WHERE id = ?
            """,
            (doc_id,)
        )

        if not result:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")

        # Construct full path
        full_path = os.path.join(settings.DOCUMENT_PATH, result["file_path"])

        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="ファイルが見つかりません")

        return FileResponse(
            path=full_path,
            media_type=result["mime_type"],
            filename=os.path.basename(result["file_path"])
        )

    except Exception as e:
        log.error(f"ドキュメントファイル取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"ドキュメントファイル取得エラー: {str(e)}")

@router.put("/{doc_id}", response_model=DocumentResponse, dependencies=[Depends(verify_api_key)])
async def update_document(
    doc_id: int = Path(..., gt=0),
    doc_update: DocumentUpdate = None,
):
    """
    Update a document's metadata.
    """
    try:
        # Check if document exists
        existing = await execute_query_single(
            "SELECT * FROM documents WHERE id = ?",
            (doc_id,)
        )

        if not existing:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")

        # Build update query
        query = "UPDATE documents SET "
        params = []
        updates = []

        if doc_update.title is not None:
            updates.append("title = ?")
            params.append(doc_update.title)

        if doc_update.doc_type is not None:
            updates.append("doc_type = ?")
            params.append(doc_update.doc_type)

            # If doc_type changed, update feedback
            if existing["doc_type"] != doc_update.doc_type:
                await execute_insert(
                    """
                    INSERT INTO feedback (document_id, original_classification, corrected_classification, feedback_date, applied)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (doc_id, existing["doc_type"], doc_update.doc_type, datetime.now().isoformat(), False)
                )

        if doc_update.department is not None:
            updates.append("department = ?")
            params.append(doc_update.department)

        if doc_update.status is not None:
            updates.append("status = ?")
            params.append(doc_update.status)

        # Always update updated_at
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())

        # Add WHERE clause
        query += ", ".join(updates) + " WHERE id = ?"
        params.append(doc_id)

        # Execute update
        success = await execute_update(query, params)

        if not success:
            raise HTTPException(status_code=500, detail="ドキュメント更新に失敗しました")

        # Get updated document
        result = await execute_query_single(
            """
            SELECT id, title, doc_type, file_path, file_size, mime_type,
                   created_at, updated_at, status, department, uploader
            FROM documents
            WHERE id = ?
            """,
            (doc_id,)
        )

        # Convert to response model
        response = {
            "id": result["id"],
            "title": result["title"],
            "doc_type": result["doc_type"],
            "file_size": result["file_size"],
            "mime_type": result["mime_type"],
            "created_at": datetime.fromisoformat(result["created_at"]),
            "updated_at": datetime.fromisoformat(result["updated_at"]),
            "department": result["department"],
            "status": result["status"],
            "uploader": result["uploader"],
        }

        # Get fields if any
        fields = await execute_query(
            """
            SELECT field_name, field_value, confidence
            FROM document_fields
            WHERE document_id = ?
            """,
            (doc_id,)
        )

        if fields:
            response["fields"] = [
                {
                    "field_name": field["field_name"],
                    "field_value": field["field_value"],
                    "confidence": field["confidence"]
                }
                for field in fields
            ]

        return response

    except Exception as e:
        log.error(f"ドキュメント更新エラー: {e}")
        raise HTTPException(status_code=500, detail=f"ドキュメント更新エラー: {str(e)}")

@router.delete("/{doc_id}", dependencies=[Depends(verify_api_key)])
async def delete_document(
    doc_id: int = Path(..., gt=0),
    permanent: bool = Query(False),
):
    """
    Delete a document or mark it as deleted.
    """
    try:
        # Get document
        document = await execute_query_single(
            "SELECT * FROM documents WHERE id = ?",
            (doc_id,)
        )

        if not document:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")

        if permanent:
            # Permanently delete from DB and file system
            success = await execute_transaction([
                ("DELETE FROM document_fields WHERE document_id = ?", (doc_id,)),
                ("DELETE FROM document_content WHERE document_id = ?", (doc_id,)),
                ("DELETE FROM document_relations WHERE document_id = ? OR related_document_id = ?", (doc_id, doc_id)),
                ("DELETE FROM feedback WHERE document_id = ?", (doc_id,)),
                ("DELETE FROM documents WHERE id = ?", (doc_id,)),
            ])

            if success:
                # Delete file
                full_path = os.path.join(settings.DOCUMENT_PATH, document["file_path"])
                if os.path.exists(full_path):
                    os.remove(full_path)

                return {"message": "ドキュメントを完全に削除しました"}
            else:
                raise HTTPException(status_code=500, detail="ドキュメント削除に失敗しました")
        else:
            # Just mark as deleted
            success = await execute_update(
                "UPDATE documents SET status = ?, updated_at = ? WHERE id = ?",
                ("deleted", datetime.now().isoformat(), doc_id)
            )

            if success:
                return {"message": "ドキュメントを削除済みとしてマークしました"}
            else:
                raise HTTPException(status_code=500, detail="ドキュメント状態の更新に失敗しました")

    except Exception as e:
        log.error(f"ドキュメント削除エラー: {e}")
        raise HTTPException(status_code=500, detail=f"ドキュメント削除エラー: {str(e)}")

@router.post("/{doc_id}/feedback", response_model=FeedbackResponse, dependencies=[Depends(verify_api_key)])
async def add_feedback(
    doc_id: int = Path(..., gt=0),
    feedback: FeedbackCreate = None,
):
    """
    Add feedback for document classification.
    """
    try:
        # Check if document exists
        document = await execute_query_single(
            "SELECT doc_type FROM documents WHERE id = ?",
            (doc_id,)
        )

        if not document:
            raise HTTPException(status_code=404, detail="ドキュメントが見つかりません")

        # If original_classification not provided, use current doc_type
        original_classification = feedback.original_classification or document["doc_type"]

        # Insert feedback
        now = datetime.now().isoformat()
        feedback_id = await execute_insert(
            """
            INSERT INTO feedback
            (document_id, original_classification, corrected_classification, feedback_date, applied)
            VALUES (?, ?, ?, ?, ?)
            """,
            (doc_id, original_classification, feedback.corrected_classification, now, False)
        )

        if not feedback_id:
            raise HTTPException(status_code=500, detail="フィードバック登録に失敗しました")

        # Update document type
        await execute_update(
            "UPDATE documents SET doc_type = ?, updated_at = ? WHERE id = ?",
            (feedback.corrected_classification, now, doc_id)
        )

        # Return created feedback
        return {
            "id": feedback_id,
            "document_id": doc_id,
            "original_classification": original_classification,
            "corrected_classification": feedback.corrected_classification,
            "feedback_date": datetime.fromisoformat(now),
            "applied": False
        }

    except Exception as e:
        log.error(f"フィードバック登録エラー: {e}")
        raise HTTPException(status_code=500, detail=f"フィードバック登録エラー: {str(e)}")