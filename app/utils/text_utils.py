# app/utils/text_utils.py
import re
import unicodedata
from typing import List, Dict, Any, Optional
import json
import string
import datetime
import os
import csv
import io

from app.core.logger import log


def normalize_text(text: str) -> str:
    """
    Normalize text by removing extra whitespace and normalizing Unicode.

    Args:
        text: Input text

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Normalize Unicode
    text = unicodedata.normalize("NFKC", text)

    # Replace tabs and newlines with spaces
    text = re.sub(r'[\t\n\r]+', ' ', text)

    # Remove extra spaces
    text = re.sub(r' +', ' ', text)

    # Trim
    text = text.strip()

    return text


def extract_date(text: str) -> Optional[datetime.date]:
    """
    Extract date from text.

    Args:
        text: Input text

    Returns:
        Extracted date or None if not found
    """
    # Try common Japanese date formats
    patterns = [
        # YYYY年MM月DD日
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',
        # YYYY/MM/DD
        r'(\d{4})/(\d{1,2})/(\d{1,2})',
        # YYYY-MM-DD
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))

                # Validate date
                if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                    return datetime.date(year, month, day)
            except ValueError:
                # Invalid date, try next pattern
                continue

    return None


def extract_amount(text: str) -> Optional[int]:
    """
    Extract monetary amount from text.

    Args:
        text: Input text

    Returns:
        Extracted amount in integers or None if not found
    """
    # Try to find amount patterns in Japanese
    patterns = [
        # Amount with yen symbol: 10,000円 or ¥10,000
        r'(¥|￥|\$)?\s*([\d,]+)(\s*円)?',
        # Amount with "total": 合計 10,000円
        r'合計\s*[：:]\s*(¥|￥|\$)?\s*([\d,]+)(\s*円)?',
        # Amount: 金額 10,000円
        r'金額\s*[：:]\s*(¥|￥|\$)?\s*([\d,]+)(\s*円)?',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                # Extract amount (depends on which group contains the number)
                amount_str = None
                for group in range(1, len(match.groups()) + 1):
                    if match.group(group) and re.search(r'\d', match.group(group)):
                        amount_str = match.group(group)
                        break

                if amount_str:
                    # Remove non-digit characters
                    amount_str = re.sub(r'[^\d]', '', amount_str)
                    return int(amount_str)
            except ValueError:
                # Invalid amount, try next pattern
                continue

    return None


def extract_company_name(text: str) -> Optional[str]:
    """
    Extract company name from text.

    Args:
        text: Input text

    Returns:
        Extracted company name or None if not found
    """
    # Try common patterns for Japanese company names
    patterns = [
        # Company name with 株式会社
        r'株式会社\s*([^\n\r]{1,30})',
        # Company name with 有限会社
        r'有限会社\s*([^\n\r]{1,30})',
        # Company name with Corp. or Inc.
        r'([^\n\r]{1,30})\s+(Corp\.|Inc\.|Corporation|Incorporated)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            company_name = match.group(1).strip()
            if company_name:
                return company_name

    return None


def extract_keywords(text: str, min_length: int = 2, max_count: int = 10) -> List[str]:
    """
    Extract important keywords from text.

    Args:
        text: Input text
        min_length: Minimum keyword length
        max_count: Maximum number of keywords to return

    Returns:
        List of keywords
    """
    if not text:
        return []

    # Simple keyword extraction based on frequency
    # This is a naive approach; in a real application,
    # you'd use a proper NLP library like spaCy or MeCab for Japanese

    # Normalize and tokenize
    text = normalize_text(text)

    # Split into words
    # This is very naive for Japanese; a proper tokenizer would be better
    words = re.findall(r'\w+', text)

    # Filter short words and count frequencies
    word_counts = {}
    for word in words:
        if len(word) >= min_length:
            word_counts[word] = word_counts.get(word, 0) + 1

    # Sort by frequency and take top N
    keywords = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in keywords[:max_count]]


def highlight_text(text: str, query: str, pre_tag: str = "<em>", post_tag: str = "</em>") -> str:
    """
    Highlight query terms in text.

    Args:
        text: Original text
        query: Search query
        pre_tag: Tag to insert before matching text
        post_tag: Tag to insert after matching text

    Returns:
        Text with highlighted terms
    """
    if not text or not query:
        return text

    # Normalize query
    query = normalize_text(query)

    # Split query into terms
    terms = query.split()

    # Highlight each term
    result = text
    for term in terms:
        if not term:
            continue

        # Create pattern with word boundary
        pattern = r'\b' + re.escape(term) + r'\b'
        result = re.sub(
            pattern,
            f"{pre_tag}\\g<0>{post_tag}",
            result,
            flags=re.IGNORECASE
        )

    return result


def extract_snippet(text: str, query: str, length: int = 200) -> str:
    """
    Extract a relevant snippet from text containing the query terms.

    Args:
        text: Original text
        query: Search query
        length: Maximum snippet length

    Returns:
        Text snippet
    """
    if not text or not query:
        return text[:length] + "..." if len(text) > length else text

    # Normalize query
    query = normalize_text(query)

    # Split query into terms
    terms = query.split()

    # Find the first occurrence of any term
    first_pos = len(text)
    for term in terms:
        if not term:
            continue

        match = re.search(r'\b' + re.escape(term) + r'\b', text, re.IGNORECASE)
        if match and match.start() < first_pos:
            first_pos = match.start()

    # If no term found, return beginning of text
    if first_pos == len(text):
        return text[:length] + "..." if len(text) > length else text

    # Calculate snippet start and end positions
    half_length = length // 2
    start = max(0, first_pos - half_length)
    end = min(len(text), start + length)

    # Adjust start if we're near the end of the text
    if end == len(text) and length < len(text):
        start = max(0, end - length)

    # Extract snippet
    snippet = text[start:end]

    # Add ellipsis if needed
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."

    return snippet


def normalize_japanese(text: str) -> str:
    """
    Normalize Japanese text (e.g., convert full-width to half-width for alphanumeric).

    Args:
        text: Input text

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Normalize Unicode
    text = unicodedata.normalize("NFKC", text)

    return text


def parse_csv_text(csv_text: str) -> List[Dict[str, Any]]:
    """
    Parse CSV text into a list of dictionaries.

    Args:
        csv_text: CSV text

    Returns:
        List of dictionaries with column names as keys
    """
    result = []

    try:
        f = io.StringIO(csv_text)
        reader = csv.DictReader(f)
        for row in reader:
            result.append(dict(row))
    except Exception as e:
        log.error(f"CSV解析エラー: {e}")

    return result


def is_japanese(text: str) -> bool:
    """
    Check if text contains Japanese characters.

    Args:
        text: Input text

    Returns:
        True if text contains Japanese characters, False otherwise
    """
    # Check for Japanese character ranges
    for char in text:
        # Hiragana
        if 0x3040 <= ord(char) <= 0x309F:
            return True
        # Katakana
        if 0x30A0 <= ord(char) <= 0x30FF:
            return True
        # CJK Unified Ideographs (Kanji)
        if 0x4E00 <= ord(char) <= 0x9FFF:
            return True

    return False


def clean_text_for_search(text: str) -> str:
    """
    Clean text for search indexing.

    Args:
        text: Input text

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Normalize Unicode
    text = unicodedata.normalize("NFKC", text)

    # Remove special characters
    text = re.sub(r'[^\w\s]', ' ', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Trim
    text = text.strip()

    return text