# app/services/document_processor.py
import os
import re
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import mimetypes
import asyncio
from pathlib import Path
import tempfile

from fastapi import UploadFile
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import aiofiles

from app.core.logger import log
from app.core.config import settings
from app.core.database import execute_insert, execute_query_single, execute_update, execute_transaction
from app.services.classifier import classify_document
from app.utils.file_utils import save_uploaded_file, detect_mimetype, is_allowed_mimetype, create_thumbnail
from app.utils.text_utils import normalize_text, extract_date, extract_amount, extract_company_name

# Configure pytesseract
if hasattr(settings, "TESSERACT_CMD") and settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


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


async def extract_fields_by_type(text: str, doc_type: str) -> List[Dict[str, Any]]:
    """
    Extract fields from text based on document type.

    Args:
        text: Document text
        doc_type: Document type

    Returns:
        List of extracted fields
    """
    extracted_fields = []

    # Get classifier config (assuming it's loaded elsewhere)
    classifier_config = await get_classifier_config()
    if not classifier_config:
        return extracted_fields

    # Find document type configuration
    doc_type_config = None
    for type_config in classifier_config.get("document_types", []):
        if type_config.get("name") == doc_type:
            doc_type_config = type_config
            break

    if not doc_type_config:
        return extracted_fields

    # Extract using patterns
    for pattern_config in doc_type_config.get("patterns", []):
        field_name = pattern_config.get("field")
        regex = pattern_config.get("regex")

        if field_name and regex:
            matches = re.finditer(regex, text)
            for match in matches:
                if match.groups():
                    # Use the first capturing group as the value
                    value = match.group(1)
                    extracted_fields.append({
                        "field_name": field_name,
                        "field_value": value,
                        "confidence": 0.9  # High confidence for regex matches
                    })
                    break  # Just use the first match

    # Add common fields if not already extracted
    field_names = [field["field_name"] for field in extracted_fields]

    # Extract date if not already extracted
    if "date" not in field_names:
        date = extract_date(text)
        if date:
            extracted_fields.append({
                "field_name": "date",
                "field_value": date.isoformat(),
                "confidence": 0.8
            })

    # Extract amount if not already extracted
    if "amount" not in field_names and doc_type in ["invoice", "quotation", "receipt"]:
        amount = extract_amount(text)
        if amount:
            extracted_fields.append({
                "field_name": "amount",
                "field_value": str(amount),
                "confidence": 0.8
            })

    # Extract company name if not already extracted
    if "company" not in field_names:
        company = extract_company_name(text)
        if company:
            extracted_fields.append({
                "field_name": "company",
                "field_value": company,
                "confidence": 0.7
            })

    return extracted_fields


async def get_classifier_config() -> Dict[str, Any]:
    """
    Get classifier configuration.

    Returns:
        Classifier configuration
    """
    try:
        import yaml

        config_path = os.path.join("config", "classifier_config.yaml")
        if not os.path.exists(config_path):
            log.warning(f"分類器設定ファイルが見つかりません: {config_path}")
            return {}

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return config

    except Exception as e:
        log.error(f"分類器設定ロードエラー: {e}")
        return {}


async def extract_text(file_path: str, mime_type: str = None) -> Optional[str]:
    """
    Extract text from a document file.

    Args:
        file_path: Path to document file
        mime_type: MIME type of the file

    Returns:
        Extracted text or None if extraction failed
    """
    if not os.path.exists(file_path):
        log.error(f"ファイルが見つかりません: {file_path}")
        return None

    if not mime_type:
        mime_type = detect_mimetype(file_path)

    try:
        text = None

        # Extract text based on file type
        if mime_type == "application/pdf":
            text = await extract_text_from_pdf(file_path)
        elif mime_type.startswith("image/"):
            text = await extract_text_from_image(file_path)
        elif mime_type in ["text/plain", "text/csv", "text/html"]:
            async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = await f.read()
        elif mime_type in ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            # For Word documents, we would need additional libraries
            # This is a placeholder for future implementation
            log.warning(f"Word文書のテキスト抽出は未実装です: {file_path}")
            return None

        if text:
            # Normalize text
            text = normalize_text(text)
            return text

        return None

    except Exception as e:
        log.error(f"テキスト抽出エラー ({mime_type}): {e}")
        return None


async def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """
    Extract text from a PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text or None if extraction failed
    """
    try:
        # First, try to extract text directly from PDF
        # This would work if the PDF has a text layer
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, extract_text_from_pdf_sync, file_path)

        # If no text found, try OCR
        if not text or len(text.strip()) < 100:  # Arbitrary threshold
            log.info(f"PDFからのテキスト抽出結果が不十分なためOCRを試行: {file_path}")
            text = await extract_text_from_pdf_ocr(file_path)

        return text

    except Exception as e:
        log.error(f"PDF テキスト抽出エラー: {e}")
        return None


def extract_text_from_pdf_sync(file_path: str) -> Optional[str]:
    """
    Extract text directly from PDF (synchronous version).

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text or None if extraction failed
    """
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text:
                    text_parts.append(page_text)

        return "\n\n".join(text_parts)

    except Exception as e:
        log.error(f"PDF直接テキスト抽出エラー: {e}")
        return None


async def extract_text_from_pdf_ocr(file_path: str) -> Optional[str]:
    """
    Extract text from a PDF file using OCR.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text or None if extraction failed
    """
    try:
        # Convert PDF to images
        loop = asyncio.get_running_loop()
        images = await loop.run_in_executor(
            None,
            lambda: convert_from_path(file_path)
        )

        if not images:
            return None

        # Process each image with OCR
        text_parts = []
        for i, image in enumerate(images):
            # Save image to temporary file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
                image.save(tmp_path, "PNG")

            # Extract text from image
            try:
                page_text = await extract_text_from_image(tmp_path)
                if page_text:
                    text_parts.append(page_text)
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        return "\n\n".join(text_parts)

    except Exception as e:
        log.error(f"PDF OCRエラー: {e}")
        return None


async def extract_text_from_image(file_path: str) -> Optional[str]:
    """
    Extract text from an image file using OCR.

    Args:
        file_path: Path to image file

    Returns:
        Extracted text or None if extraction failed
    """
    try:
        # Run OCR in a separate thread to avoid blocking
        loop = asyncio.get_running_loop()

        # Determine language
        lang = settings.OCR_LANGUAGE if hasattr(settings, "OCR_LANGUAGE") else "jpn+eng"

        text = await loop.run_in_executor(
            None,
            lambda: pytesseract.image_to_string(
                Image.open(file_path),
                lang=lang
            )
        )

        return text

    except Exception as e:
        log.error(f"画像 OCRエラー: {e}")
        return None