# app/services/ocr_service.py
import os
import asyncio
import tempfile
from typing import List, Dict, Any, Optional, Tuple
import concurrent.futures
import time

import pytesseract
from PIL import Image
from pdf2image import convert_from_path

from app.core.logger import log
from app.core.config import settings

# Configure pytesseract
if hasattr(settings, "TESSERACT_CMD") and settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

# Thread pool for CPU-bound OCR operations
_thread_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=min(4, os.cpu_count() or 2)
)


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


async def process_image(file_path: str, language: str) -> Optional[str]:
    """
    Process a single image with OCR.

    Args:
        file_path: Path to image file
        language: OCR language code

    Returns:
        Extracted text or None if processing failed
    """
    try:
        # Run OCR in thread pool
        loop = asyncio.get_running_loop()

        start_time = time.time()
        text = await loop.run_in_executor(
            _thread_pool,
            lambda: pytesseract.image_to_string(
                Image.open(file_path),
                lang=language
            )
        )
        processing_time = time.time() - start_time

        log.info(f"OCR画像処理完了: {file_path} ({processing_time:.2f}秒)")
        return text

    except Exception as e:
        log.error(f"画像OCR処理エラー: {e}")
        return None


async def process_pdf(file_path: str, language: str) -> Optional[str]:
    """
    Process a PDF file with OCR.

    Args:
        file_path: Path to PDF file
        language: OCR language code

    Returns:
        Extracted text or None if processing failed
    """
    try:
        loop = asyncio.get_running_loop()

        # Convert PDF to images in thread pool
        start_time = time.time()
        images = await loop.run_in_executor(
            _thread_pool,
            lambda: convert_from_path(
                file_path,
                dpi=300,  # Higher DPI for better OCR
                thread_count=1  # Single thread since we're already using a thread pool
            )
        )

        if not images:
            log.warning(f"PDFから画像への変換結果が空です: {file_path}")
            return None

        # Process each image with OCR
        text_parts = []
        for i, image in enumerate(images):
            # Create a temporary file for the image
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            # Save image to temporary file
            image.save(tmp_path, format="PNG")

            try:
                # Process the image
                page_text = await process_image(tmp_path, language)
                if page_text:
                    text_parts.append(f"--- Page {i+1} ---\n{page_text}")
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        processing_time = time.time() - start_time
        log.info(f"OCR PDF処理完了: {file_path} ({len(images)}ページ, {processing_time:.2f}秒)")

        return "\n\n".join(text_parts)

    except Exception as e:
        log.error(f"PDF OCR処理エラー: {e}")
        return None


async def preprocess_image(image_path: str) -> Optional[str]:
    """
    Preprocess image before OCR to improve text recognition.

    Args:
        image_path: Path to image file

    Returns:
        Path to preprocessed image or None if preprocessing failed
    """
    try:
        from PIL import Image, ImageFilter, ImageEnhance

        # Open image
        with Image.open(image_path) as img:
            # Convert to grayscale
            img = img.convert('L')

            # Resize for better OCR if image is very large
            max_size = 3000  # Max dimension
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            # Enhance contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)  # Increase contrast

            # Apply slight sharpening
            img = img.filter(ImageFilter.SHARPEN)

            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
                img.save(tmp_path, format="PNG")

            return tmp_path

    except Exception as e:
        log.error(f"画像前処理エラー: {e}")
        return None


async def ocr_with_confidence(file_path: str, language: str = None) -> Tuple[Optional[str], float]:
    """
    Process OCR and estimate confidence level.

    Args:
        file_path: Path to file
        language: OCR language code

    Returns:
        Tuple of (extracted text, confidence score) or (None, 0.0) if failed
    """
    try:
        # Process OCR
        text = await process_ocr(file_path, language)

        if not text:
            return None, 0.0

        # Estimate confidence (this is a simplified approach)
        # In a production environment, you might use more sophisticated methods
        confidence = estimate_ocr_confidence(text)

        return text, confidence

    except Exception as e:
        log.error(f"OCR処理エラー (信頼度付き): {e}")
        return None, 0.0


def estimate_ocr_confidence(text: str) -> float:
    """
    Estimate OCR confidence based on text characteristics.

    Args:
        text: OCR result text

    Returns:
        Estimated confidence score (0.0-1.0)
    """
    if not text:
        return 0.0

    # This is a very simplistic approach to estimating confidence
    # In a real application, you'd use more sophisticated methods

    # Calculate ratio of non-alphanumeric characters (higher ratio might indicate OCR errors)
    non_alnum_ratio = sum(not c.isalnum() and not c.isspace() for c in text) / max(1, len(text))

    # Very high ratio of special characters often indicates poor OCR
    if non_alnum_ratio > 0.5:
        base_conf = 0.3
    elif non_alnum_ratio > 0.3:
        base_conf = 0.5
    else:
        base_conf = 0.8

    # Adjust based on text length (very short results often indicate poor OCR)
    if len(text) < 10:
        base_conf *= 0.5
    elif len(text) < 50:
        base_conf *= 0.8

    return min(1.0, base_conf)


async def is_ocr_available() -> bool:
    """
    Check if OCR is available.

    Returns:
        True if OCR is available, False otherwise
    """
    try:
        # Try to get tesseract version
        loop = asyncio.get_running_loop()
        version = await loop.run_in_executor(
            _thread_pool,
            lambda: pytesseract.get_tesseract_version()
        )

        return version is not None

    except Exception:
        return False


async def get_available_languages() -> List[str]:
    """
    Get list of available OCR languages.

    Returns:
        List of language codes
    """
    try:
        # Get list of available languages
        loop = asyncio.get_running_loop()
        langs = await loop.run_in_executor(
            _thread_pool,
            lambda: pytesseract.get_languages()
        )

        return langs

    except Exception:
        return []