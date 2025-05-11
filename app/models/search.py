# app/models/search.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date

class SearchQuery(BaseModel):
    """Search query model."""
    query_text: Optional[str] = None
    doc_type: Optional[str] = None
    department: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    uploader: Optional[str] = None
    status: Optional[str] = "active"
    include_archives: bool = False
    page: int = 1
    per_page: int = 20

    class Config:
        schema_extra = {
            "example": {
                "total": 42,
                "page": 1,
                "per_page": 20,
                "total_pages": 3,
                "results": [
                    {
                        "id": 1,
                        "title": "請求書_2023年3月",
                        "doc_type": "invoice",
                        "file_size": 145678,
                        "mime_type": "application/pdf",
                        "created_at": "2023-03-15T10:30:00",
                        "updated_at": "2023-03-15T10:30:00",
                        "department": "営業部",
                        "status": "active",
                        "uploader": "user1",
                        "snippet": "...<em>請求書</em>の内容...",
                        "relevance": 0.92,
                        "fields": {
                            "amount": "150000",
                            "date": "2023-03-01"
                        }
                    }
                ],
                "query": {
                    "query_text": "請求書",
                    "doc_type": "invoice",
                    "page": 1,
                    "per_page": 20
                },
                "execution_time": 0.135
            }
        }
        schema_extra = {
            "example": {
                "query_text": "請求書",
                "doc_type": "invoice",
                "department": "営業部",
                "date_from": "2023-01-01",
                "date_to": "2023-12-31",
                "include_archives": False,
                "page": 1,
                "per_page": 20
            }
        }

class AdvancedSearchQuery(SearchQuery):
    """Advanced search query model with additional filters."""
    field_filters: Optional[Dict[str, Any]] = None
    sort_by: Optional[str] = "created_at"
    sort_order: Optional[str] = "desc"

    class Config:
        schema_extra = {
            "example": {
                "query_text": "請求書",
                "doc_type": "invoice",
                "department": "営業部",
                "date_from": "2023-01-01",
                "date_to": "2023-12-31",
                "field_filters": {
                    "amount": ">10000",
                    "company": "株式会社ABC"
                },
                "sort_by": "created_at",
                "sort_order": "desc",
                "include_archives": False,
                "page": 1,
                "per_page": 20
            }
        }

class SearchResult(BaseModel):
    """Search result model."""
    id: int
    title: str
    doc_type: Optional[str] = None
    file_size: int
    mime_type: str
    created_at: datetime
    updated_at: datetime
    department: Optional[str] = None
    status: str
    uploader: Optional[str] = None
    snippet: Optional[str] = None
    relevance: Optional[float] = None
    fields: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True

class SearchResponse(BaseModel):
    """Search response model."""
    total: int
    page: int
    per_page: int
    total_pages: int
    results: List[SearchResult]
    query: SearchQuery
    execution_time: float  # in seconds

    class Config: