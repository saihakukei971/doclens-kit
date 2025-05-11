# app/api/search.py
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import List, Optional, Dict, Any
import time
from datetime import datetime, date
import math

from app.core.logger import log
from app.core.config import settings
from app.core.security import verify_api_key
from app.core.database import execute_query, execute_query_single
from app.models.search import SearchQuery, AdvancedSearchQuery, SearchResponse, SearchResult
from app.services.search_service import build_search_query, highlight_content, search_archives

router = APIRouter()

@router.post("/", response_model=SearchResponse, dependencies=[Depends(verify_api_key)])
async def search_documents(
    search_query: SearchQuery = Body(...),
):
    """
    Search documents with text and filters.
    """
    try:
        start_time = time.time()

        # Build search query
        query, params, select_clause = build_search_query(search_query)

        # Get total count (without pagination)
        count_query = f"""
        SELECT COUNT(*) as total
        FROM documents d
        {query}
        """

        count_result = await execute_query_single(count_query, params)
        total = count_result["total"] if count_result else 0

        # Add pagination to query
        paginated_query = f"""
        {select_clause}
        FROM documents d
        {query}
        ORDER BY d.created_at DESC
        LIMIT ? OFFSET ?
        """

        pagination_params = params.copy()
        pagination_params.append(search_query.per_page)
        pagination_params.append((search_query.page - 1) * search_query.per_page)

        # Execute search
        results = await execute_query(paginated_query, pagination_params)

        # Prepare search results
        search_results = []
        for result in results:
            # Get document content for highlighting if query text is provided
            snippet = None
            if search_query.query_text and search_query.query_text.strip():
                content_result = await execute_query_single(
                    """
                    SELECT content
                    FROM document_content
                    WHERE document_id = ?
                    """,
                    (result["id"],)
                )

                if content_result and content_result["content"]:
                    snippet = highlight_content(
                        content_result["content"],
                        search_query.query_text,
                        max_length=200
                    )

            # Get fields
            fields = None
            fields_result = await execute_query(
                """
                SELECT field_name, field_value, confidence
                FROM document_fields
                WHERE document_id = ?
                """,
                (result["id"],)
            )

            if fields_result:
                fields = {
                    field["field_name"]: field["field_value"]
                    for field in fields_result
                }

            # Create search result
            search_result = {
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
                "snippet": snippet,
                "relevance": result.get("relevance"),
                "fields": fields,
            }
            search_results.append(search_result)

        # Search in archives if requested
        archive_results = []
        if search_query.include_archives and search_query.query_text:
            archive_results = await search_archives(search_query)

            # Add archive results to search results
            search_results.extend(archive_results)

            # Update total count
            total += len(archive_results)

        # Calculate total pages
        total_pages = math.ceil(total / search_query.per_page) if total > 0 else 1

        # Calculate execution time
        execution_time = time.time() - start_time

        # Prepare response
        response = {
            "total": total,
            "page": search_query.page,
            "per_page": search_query.per_page,
            "total_pages": total_pages,
            "results": search_results,
            "query": search_query,
            "execution_time": execution_time,
        }

        return response

    except Exception as e:
        log.error(f"検索エラー: {e}")
        raise HTTPException(status_code=500, detail=f"検索エラー: {str(e)}")

@router.post("/advanced", response_model=SearchResponse, dependencies=[Depends(verify_api_key)])
async def advanced_search(
    search_query: AdvancedSearchQuery = Body(...),
):
    """
    Advanced search with additional filters and options.
    """
    try:
        start_time = time.time()

        # Build search query
        query, params, select_clause = build_search_query(search_query)

        # Add field filters if provided
        if search_query.field_filters:
            for field_name, field_value in search_query.field_filters.items():
                query += """
                AND EXISTS (
                    SELECT 1 FROM document_fields df
                    WHERE df.document_id = d.id
                    AND df.field_name = ?
                """
                params.append(field_name)

                # Check if it's a comparison operator
                if isinstance(field_value, str) and any(op in field_value for op in ['>', '<', '=', '!=', '>=', '<=']):
                    op = None
                    value = field_value

                    for operator in ['>=', '<=', '>', '<', '=', '!=']:
                        if field_value.startswith(operator):
                            op = operator
                            value = field_value[len(operator):].strip()
                            break

                    if op:
                        query += f" AND CAST(df.field_value AS NUMERIC) {op} ? )"
                        try:
                            params.append(float(value))
                        except ValueError:
                            params.append(value)
                    else:
                        query += " AND df.field_value = ? )"
                        params.append(field_value)
                else:
                    query += " AND df.field_value = ? )"
                    params.append(str(field_value))

        # Get total count (without pagination)
        count_query = f"""
        SELECT COUNT(*) as total
        FROM documents d
        {query}
        """

        count_result = await execute_query_single(count_query, params)
        total = count_result["total"] if count_result else 0

        # Add sort options
        sort_field = search_query.sort_by if search_query.sort_by else "created_at"
        sort_order = search_query.sort_order.upper() if search_query.sort_order else "DESC"

        if sort_order not in ["ASC", "DESC"]:
            sort_order = "DESC"

        # Validate sort field to prevent SQL injection
        allowed_sort_fields = ["created_at", "updated_at", "title", "doc_type", "file_size"]
        if sort_field not in allowed_sort_fields:
            sort_field = "created_at"

        # Add pagination and sorting to query
        paginated_query = f"""
        {select_clause}
        FROM documents d
        {query}
        ORDER BY d.{sort_field} {sort_order}
        LIMIT ? OFFSET ?
        """

        pagination_params = params.copy()
        pagination_params.append(search_query.per_page)
        pagination_params.append((search_query.page - 1) * search_query.per_page)

        # Execute search
        results = await execute_query(paginated_query, pagination_params)

        # Prepare search results
        search_results = []
        for result in results:
            # Get document content for highlighting if query text is provided
            snippet = None
            if search_query.query_text and search_query.query_text.strip():
                content_result = await execute_query_single(
                    """
                    SELECT content
                    FROM document_content
                    WHERE document_id = ?
                    """,
                    (result["id"],)
                )

                if content_result and content_result["content"]:
                    snippet = highlight_content(
                        content_result["content"],
                        search_query.query_text,
                        max_length=200
                    )

            # Get fields
            fields = None
            fields_result = await execute_query(
                """
                SELECT field_name, field_value, confidence
                FROM document_fields
                WHERE document_id = ?
                """,
                (result["id"],)
            )

            if fields_result:
                fields = {
                    field["field_name"]: field["field_value"]
                    for field in fields_result
                }

            # Create search result
            search_result = {
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
                "snippet": snippet,
                "relevance": result.get("relevance"),
                "fields": fields,
            }
            search_results.append(search_result)

        # Search in archives if requested
        archive_results = []
        if search_query.include_archives and search_query.query_text:
            archive_results = await search_archives(search_query)

            # Add archive results to search results
            search_results.extend(archive_results)

            # Update total count
            total += len(archive_results)

        # Calculate total pages
        total_pages = math.ceil(total / search_query.per_page) if total > 0 else 1

        # Calculate execution time
        execution_time = time.time() - start_time

        # Prepare response
        response = {
            "total": total,
            "page": search_query.page,
            "per_page": search_query.per_page,
            "total_pages": total_pages,
            "results": search_results,
            "query": search_query.dict(),
            "execution_time": execution_time,
        }

        return response

    except Exception as e:
        log.error(f"高度検索エラー: {e}")
        raise HTTPException(status_code=500, detail=f"高度検索エラー: {str(e)}")

@router.get("/fields", dependencies=[Depends(verify_api_key)])
async def get_field_values(
    field_name: str = Query(...),
    doc_type: Optional[str] = Query(None),
):
    """
    Get unique values for a specific field.
    """
    try:
        # Build query
        query = """
        SELECT DISTINCT field_value
        FROM document_fields df
        JOIN documents d ON df.document_id = d.id
        WHERE df.field_name = ?
        AND d.status = 'active'
        """
        params = [field_name]

        if doc_type:
            query += " AND d.doc_type = ?"
            params.append(doc_type)

        # Execute query
        results = await execute_query(query, params)

        # Extract values
        values = [result["field_value"] for result in results]

        return {"field_name": field_name, "values": values}

    except Exception as e:
        log.error(f"フィールド値取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"フィールド値取得エラー: {str(e)}")

@router.get("/document-types", dependencies=[Depends(verify_api_key)])
async def get_document_types():
    """
    Get all unique document types.
    """
    try:
        # Execute query
        results = await execute_query(
            """
            SELECT DISTINCT doc_type
            FROM documents
            WHERE doc_type IS NOT NULL
            AND status = 'active'
            """
        )

        # Extract types
        types = [result["doc_type"] for result in results]

        return {"types": types}

    except Exception as e:
        log.error(f"文書タイプ取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"文書タイプ取得エラー: {str(e)}")

@router.get("/departments", dependencies=[Depends(verify_api_key)])
async def get_departments():
    """
    Get all unique departments.
    """
    try:
        # Execute query
        results = await execute_query(
            """
            SELECT DISTINCT department
            FROM documents
            WHERE department IS NOT NULL
            AND status = 'active'
            """
        )

        # Extract departments
        departments = [result["department"] for result in results]

        return {"departments": departments}

    except Exception as e:
        log.error(f"部署取得エラー: {e}")
        raise HTTPException(status_code=500, detail=f"部署取得エラー: {str(e)}")