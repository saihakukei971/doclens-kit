# app/utils/file_utils.py
import os
import shutil
import mimetypes
import zipfile
import hashlib
from pathlib import Path
from datetime import datetime
import re
import aiofiles
from fastapi import UploadFile

from app.core.config import settings
from app.core.logger import log


async def save_uploaded_file(file: UploadFile, rel_path: str) -> str:
    """
    Save an uploaded file to the document storage.

    Args:
        file: Uploaded file
        rel_path: Relative path within the document storage

    Returns:
        Full path of the saved file
    """
    # Create directory if it doesn't exist
    full_dir = os.path.join(settings.DOCUMENT_PATH, os.path.dirname(rel_path))
    os.makedirs(full_dir, exist_ok=True)

    # Full path
    full_path = os.path.join(settings.DOCUMENT_PATH, rel_path)

    # Save the file
    async with aiofiles.open(full_path, 'wb') as out_file:
        # Read and write in chunks
        while content := await file.read(1024 * 1024):  # 1MB chunks
            await out_file.write(content)

    log.info(f"ファイル保存完了: {rel_path}")
    return full_path


def get_safe_filename(filename: str) -> str:
    """
    Convert a filename to a safe version that is filesystem-friendly.

    Args:
        filename: Original filename

    Returns:
        Safe filename
    """
    # Replace problematic characters
    safe_name = re.sub(r'[^\w\.-]', '_', filename)
    return safe_name


def create_unique_filename(filename: str) -> str:
    """
    Create a unique filename by adding a timestamp if necessary.

    Args:
        filename: Original filename

    Returns:
        Unique filename
    """
    name, ext = os.path.splitext(filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{name}_{timestamp}{ext}"


def detect_mimetype(file_path: str) -> str:
    """
    Detect the MIME type of a file.

    Args:
        file_path: Path to the file

    Returns:
        MIME type
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        # Default to octet-stream if cannot detect
        mime_type = "application/octet-stream"
    return mime_type


def is_allowed_mimetype(mime_type: str) -> bool:
    """
    Check if a MIME type is allowed.

    Args:
        mime_type: MIME type to check

    Returns:
        True if allowed, False otherwise
    """
    return mime_type in settings.ALLOWED_MIMETYPES


def calculate_file_hash(file_path: str) -> str:
    """
    Calculate the SHA-256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal hash
    """
    h = hashlib.sha256()

    with open(file_path, 'rb') as f:
        # Read and update in chunks
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)

    return h.hexdigest()


def is_zipfile(file_path: str) -> bool:
    """
    Check if a file is a ZIP file.

    Args:
        file_path: Path to the file

    Returns:
        True if it's a ZIP file, False otherwise
    """
    return zipfile.is_zipfile(file_path)


def list_zip_contents(file_path: str) -> list:
    """
    List the contents of a ZIP file.

    Args:
        file_path: Path to the ZIP file

    Returns:
        List of filenames in the ZIP
    """
    result = []

    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            result = zip_ref.namelist()
    except Exception as e:
        log.error(f"ZIPファイル読み取りエラー: {e}")

    return result


def make_archive(source_dir: str, dest_path: str) -> str:
    """
    Create a ZIP archive from a directory.

    Args:
        source_dir: Source directory
        dest_path: Destination ZIP file path

    Returns:
        Path to the created archive
    """
    result = shutil.make_archive(
        os.path.splitext(dest_path)[0],  # Remove .zip extension if present
        'zip',
        source_dir
    )

    log.info(f"アーカイブ作成完了: {result}")
    return result


def create_date_directory(base_path: str, date: datetime = None) -> str:
    """
    Create a directory structure based on date (YYYY/MM/DD).

    Args:
        base_path: Base path
        date: Date (defaults to current date)

    Returns:
        Created directory path
    """
    if not date:
        date = datetime.now()

    date_path = date.strftime("%Y/%m/%d")
    full_path = os.path.join(base_path, date_path)
    os.makedirs(full_path, exist_ok=True)

    return full_path


def get_directory_size(dir_path: str) -> int:
    """
    Calculate the total size of a directory.

    Args:
        dir_path: Directory path

    Returns:
        Size in bytes
    """
    total_size = 0

    for dirpath, dirnames, filenames in os.walk(dir_path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            if os.path.isfile(file_path):
                total_size += os.path.getsize(file_path)

    return total_size


def clean_directory(dir_path: str, keep_days: int = 0) -> int:
    """
    Clean a directory by removing files older than the specified days.

    Args:
        dir_path: Directory path
        keep_days: Days to keep (0 to remove all)

    Returns:
        Number of removed files
    """
    if not os.path.exists(dir_path):
        return 0

    now = datetime.now().timestamp()
    removed_count = 0

    for root, dirs, files in os.walk(dir_path):
        for name in files:
            file_path = os.path.join(root, name)
            if os.path.isfile(file_path):
                mtime = os.path.getmtime(file_path)
                age_days = (now - mtime) / (60 * 60 * 24)

                if age_days > keep_days:
                    os.remove(file_path)
                    removed_count += 1

    # Remove empty directories
    for root, dirs, files in os.walk(dir_path, topdown=False):
        for name in dirs:
            dir_path = os.path.join(root, name)
            if not os.listdir(dir_path):
                os.rmdir(dir_path)

    return removed_count


def get_file_info(file_path: str) -> dict:
    """
    Get information about a file.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary with file information
    """
    if not os.path.exists(file_path):
        return None

    stat = os.stat(file_path)
    created = datetime.fromtimestamp(stat.st_ctime)
    modified = datetime.fromtimestamp(stat.st_mtime)
    size = stat.st_size

    mime_type = detect_mimetype(file_path)

    return {
        "name": os.path.basename(file_path),
        "path": file_path,
        "size": size,
        "size_human": format_file_size(size),
        "mime_type": mime_type,
        "created": created.isoformat(),
        "modified": modified.isoformat(),
    }


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in bytes to human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def get_temp_directory() -> str:
    """
    Get a temporary directory for processing.

    Returns:
        Path to temporary directory
    """
    temp_dir = os.path.join(settings.DOCUMENT_PATH, "temp")
    os.makedirs(temp_dir, exist_ok=True)

    # Create a unique subdirectory
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_dir = os.path.join(temp_dir, f"temp_{timestamp}")
    os.makedirs(unique_dir, exist_ok=True)

    return unique_dir


def clean_temp_directories(keep_hours: int = 24) -> int:
    """
    Clean temporary directories older than the specified hours.

    Args:
        keep_hours: Hours to keep directories

    Returns:
        Number of removed directories
    """
    temp_dir = os.path.join(settings.DOCUMENT_PATH, "temp")
    if not os.path.exists(temp_dir):
        return 0

    now = datetime.now().timestamp()
    removed_count = 0

    # List all temp subdirectories
    for name in os.listdir(temp_dir):
        dir_path = os.path.join(temp_dir, name)
        if os.path.isdir(dir_path) and name.startswith("temp_"):
            mtime = os.path.getmtime(dir_path)
            age_hours = (now - mtime) / (60 * 60)

            if age_hours > keep_hours:
                try:
                    shutil.rmtree(dir_path)
                    removed_count += 1
                except Exception as e:
                    log.error(f"一時ディレクトリ削除エラー: {e}")

    return removed_count


def watch_directory(directory: str, callback) -> None:
    """
    Watch a directory for changes (placeholder for folder monitoring).

    Args:
        directory: Directory to watch
        callback: Function to call when a file is added

    Note:
        This is a placeholder. Actual implementation would use a library like watchdog
        or implement a periodic check for changes.
    """
    # This would normally be implemented with a file system watcher library
    # or by periodically checking for new files
    log.info(f"ディレクトリ監視を設定: {directory}")

    # For now, this is just a placeholder
    pass


def is_valid_file(file_path: str) -> bool:
    """
    Check if a file is valid (exists and not too large).

    Args:
        file_path: Path to the file

    Returns:
        True if valid, False otherwise
    """
    if not os.path.exists(file_path):
        return False

    if not os.path.isfile(file_path):
        return False

    # Check size
    size = os.path.getsize(file_path)
    if size > settings.UPLOAD_SIZE_LIMIT:
        return False

    # Check MIME type
    mime_type = detect_mimetype(file_path)
    if not is_allowed_mimetype(mime_type):
        return False

    return True


def create_thumbnail(file_path: str, size: tuple = (128, 128)) -> str:
    """
    Create a thumbnail for an image or PDF.

    Args:
        file_path: Path to the file
        size: Thumbnail size (width, height)

    Returns:
        Path to the thumbnail or None if not supported
    """
    try:
        from PIL import Image
        import pdf2image

        # Get file extension and MIME type
        _, ext = os.path.splitext(file_path)
        mime_type = detect_mimetype(file_path)

        # Create thumbnail directory
        thumb_dir = os.path.join(settings.DOCUMENT_PATH, "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)

        # Generate unique thumbnail name
        file_hash = calculate_file_hash(file_path)[:16]
        thumb_path = os.path.join(thumb_dir, f"{file_hash}_thumb.png")

        # Skip if thumbnail already exists
        if os.path.exists(thumb_path):
            return thumb_path

        # Process based on file type
        if mime_type.startswith("image/"):
            # Create thumbnail from image
            with Image.open(file_path) as img:
                img.thumbnail(size)
                img.save(thumb_path, "PNG")

            return thumb_path

        elif mime_type == "application/pdf":
            # Create thumbnail from first page of PDF
            images = pdf2image.convert_from_path(
                file_path,
                first_page=1,
                last_page=1,
                size=size
            )

            if images:
                images[0].save(thumb_path, "PNG")
                return thumb_path

        # Unsupported file type
        return None

    except Exception as e:
        log.error(f"サムネイル作成エラー: {e}")
        return None