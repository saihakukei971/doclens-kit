# app/core/config.py
from dynaconf import Dynaconf
import os
from pathlib import Path

# Create config directory if it doesn't exist
os.makedirs("config", exist_ok=True)

# Default configuration path
config_path = Path("config")

# Load settings from files
settings = Dynaconf(
    envvar_prefix="DATAHUB",
    settings_files=[
        config_path / "default.toml",
        config_path / ".secrets.toml",  # Optional file for secrets
    ],
    environments=True,
    load_dotenv=True,
)

# Default settings if not in file
if not hasattr(settings, "DATABASE_URL"):
    settings.DATABASE_URL = "sqlite:///data/documents.db"

if not hasattr(settings, "ARCHIVE_PATH"):
    settings.ARCHIVE_PATH = "data/archives"

if not hasattr(settings, "DOCUMENT_PATH"):
    settings.DOCUMENT_PATH = "data/documents"

if not hasattr(settings, "UPLOAD_SIZE_LIMIT"):
    settings.UPLOAD_SIZE_LIMIT = 2 * 1024 * 1024 * 1024  # 2GB

if not hasattr(settings, "ALLOWED_MIMETYPES"):
    settings.ALLOWED_MIMETYPES = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/csv",
    ]

if not hasattr(settings, "MONITORED_FOLDERS"):
    settings.MONITORED_FOLDERS = []  # Add paths to monitor

if not hasattr(settings, "OCR_ENABLED"):
    settings.OCR_ENABLED = True

if not hasattr(settings, "OCR_LANGUAGE"):
    settings.OCR_LANGUAGE = "jpn"  # Japanese OCR by default

# Environment-specific overrides
if settings.ENV_FOR_DYNACONF == "production":
    # Production overrides here
    pass
elif settings.ENV_FOR_DYNACONF == "development":
    # Development overrides here
    pass

# Function to validate configuration
def validate_config():
    """Validate configuration settings."""
    required_settings = [
        "DATABASE_URL",
        "ARCHIVE_PATH",
        "DOCUMENT_PATH",
    ]

    for setting in required_settings:
        if not hasattr(settings, setting) or not getattr(settings, setting):
            raise ValueError(f"Required setting {setting} is missing or empty")

    # Check paths exist
    if not os.path.exists(settings.DOCUMENT_PATH):
        os.makedirs(settings.DOCUMENT_PATH, exist_ok=True)

    if not os.path.exists(settings.ARCHIVE_PATH):
        os.makedirs(settings.ARCHIVE_PATH, exist_ok=True)

    return True