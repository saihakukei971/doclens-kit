# app/services/search_service.py
import os
import re
import sqlite3
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import glob

from app.core.logger import log
from app.core.config import settings
from app.core.database import execute_query, execute_query_single
from app.models.search import SearchQuery, AdvancedSearchQuery, SearchResponse, SearchResult
from app.utils.text_utils import normalize_text, highlight_text, extract_snippet


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


def highlight_content(content: str, query: str, max_length: int = 200) -> str:
    """
    Create a highlighted snippet from content based on query.

    Args:
        content: Full document content
        query: Search query
        max_length: Maximum snippet length

    Returns:
        Highlighted snippet
    """
    # Extract snippet
    snippet = extract_snippet(content, query, length=max_length)

    # Highlight query terms
    return highlight_text(snippet, query)


async def search_archives(search_query: SearchQuery) -> List[SearchResult]:
    """
    Search in archive databases.

    Args:
        search_query: Search query parameters

    Returns:
        List of search results from archives
    """
    results = []

    try:
        # Find archive database files
        archive_path = settings.ARCHIVE_PATH
        archive_dbs = glob.glob(os.path.join(archive_path, "**", "*.db"), recursive=True)

        # Set limit on how many archives to search
        max_archives = 5  # Limit to prevent too many DB connections

        # Search each archive
        for db_path in sorted(archive_dbs, reverse=True)[:max_archives]:
            log.info(f"アーカイブ検索: {db_path}")

            # Connect to archive database
            try:
                # Build search query
                query, params, select_clause = build_search_query(search_query)

                # Create connection to archive DB
                conn = await asyncio.to_thread(sqlite3.connect, db_path)
                conn.row_factory = sqlite3.Row

                # Check if document_content table exists
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_content'")
                if not cursor.fetchone():
                    cursor.close()
                    conn.close()
                    continue

                # Execute search
                full_query = f"{select_clause} FROM documents d {query}"
                cursor = conn.cursor()
                cursor.execute(full_query, params)
                archive_results = cursor.fetchall()

                # Process results
                for row in archive_results:
                    # Convert to dict
                    result = {key: row[key] for key in row.keys()}

                    # Get snippet if query text is provided
                    snippet = None
                    if search_query.query_text and search_query.query_text.strip():
                        content_cursor = conn.cursor()
                        content_cursor.execute(
                            "SELECT content FROM document_content WHERE document_id = ?",
                            (result["id"],)
                        )
                        content_row = content_cursor.fetchone()

                        if content_row and content_row["content"]:
                            snippet = highlight_content(
                                content_row["content"],
                                search_query.query_text,
                                max_length=200
                            )

                        content_cursor.close()

                    # Get fields
                    fields = None
                    fields_cursor = conn.cursor()
                    fields_cursor.execute(
                        """
                        SELECT field_name, field_value, confidence
                        FROM document_fields
                        WHERE document_id = ?
                        """,
                        (result["id"],)
                    )
                    fields_rows = fields_cursor.fetchall()

                    if fields_rows:
                        fields = {
                            row["field_name"]: row["field_value"]
                            for row in fields_rows
                        }

                    fields_cursor.close()

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
                        "archived": True,
                        "archive_path": db_path,
                    }

                    results.append(search_result)

                cursor.close()
                conn.close()

            except Exception as e:
                log.error(f"アーカイブDB {db_path} の検索エラー: {e}")
                continue

        return results

    except Exception as e:
        log.error(f"アーカイブ検索エラー: {e}")
        return []


async def search_by_field(field_name: str, field_value: str, doc_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search documents by specific field value.

    Args:
        field_name: Field name to search
        field_value: Field value to match
        doc_type: Optional document type filter

    Returns:
        List of matching documents
    """
    try:
        # Build query
        query = """
        SELECT d.id, d.title, d.doc_type, d.file_path, d.file_size, d.mime_type,
               d.created_at, d.updated_at, d.status, d.department, d.uploader
        FROM documents d
        JOIN document_fields df ON d.id = df.document_id
        WHERE df.field_name = ?
        AND df.field_value = ?
        AND d.status = 'active'
        """

        params = [field_name, field_value]

        if doc_type:
            query += " AND d.doc_type = ?"
            params.append(doc_type)

        # Execute query
        results = await execute_query(query, params)

        return [dict(result) for result in results]

    except Exception as e:
        log.error(f"フィールド検索エラー: {e}")
        return []


async def find_related_documents(document_id: int) -> List[Dict[str, Any]]:
    """
    Find documents related to the given document.

    Args:
        document_id: Document ID

    Returns:
        List of related documents
    """
    try:
        # Get document details
        document = await execute_query_single(
            """
            SELECT id, title, doc_type, department, uploader
            FROM documents
            WHERE id = ?
            """,
            (document_id,)
        )

        if not document:
            return []

        # Get document content
        content = await execute_query_single(
            """
            SELECT content
            FROM document_content
            WHERE document_id = ?
            """,
            (document_id,)
        )

        if not content or not content["content"]:
            return []

        # Extract keywords (simple approach)
        text = content["content"]
        keywords = extract_keywords(text)

        # Search for similar documents
        results = []
        for keyword in keywords[:3]:  # Use top 3 keywords
            query = f"""
            SELECT d.id, d.title, d.doc_type, d.file_path, d.created_at, d.department
            FROM documents d
            JOIN document_content dc ON d.id = dc.document_id
            WHERE d.id != ?
            AND dc.content MATCH ?
            AND d.status = 'active'
            LIMIT 5
            """

            keyword_results = await execute_query(query, (document_id, keyword))
            results.extend([dict(r) for r in keyword_results])

        # Remove duplicates
        unique_results = []
        seen_ids = set()
        for result in results:
            if result["id"] not in seen_ids:
                seen_ids.add(result["id"])
                unique_results.append(result)

        # Limit to top 10
        return unique_results[:10]

    except Exception as e:
        log.error(f"関連文書検索エラー: {e}")
        return []


def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    """
    Extract important keywords from text.

    Args:
        text: Input text
        max_keywords: Maximum number of keywords to extract

    Returns:
        List of keywords
    """
    try:
        from collections import Counter
        import re

        # Simple keyword extraction (naive approach)
        # In a real application, you'd use a proper NLP library

        # Normalize and tokenize
        text = normalize_text(text)

        # Remove common stop words (Japanese + English)
        stop_words = {
            "の", "に", "は", "を", "た", "が", "で", "て", "と", "し", "れ", "さ",
            "ある", "いる", "する", "ます", "です", "から", "など", "まで",
            "the", "is", "and", "of", "to", "in", "a", "for", "that", "on", "at"
        }

        # Simple word tokenization
        # This is very naive for Japanese; a proper tokenizer would be better
        words = re.findall(r'\w+', text)

        # Filter stop words and short words
        filtered_words = [word for word in words if word.lower() not in stop_words and len(word) > 1]

        # Count frequencies
        word_counts = Counter(filtered_words)

        # Get top keywords
        return [word for word, _ in word_counts.most_common(max_keywords)]

    except Exception as e:
        log.error(f"キーワード抽出エラー: {e}")
        return []