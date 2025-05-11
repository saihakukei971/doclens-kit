# app/core/logger.py
from loguru import logger
import os
import sys

# Create log directory
os.makedirs("logs", exist_ok=True)

# Logger configuration
logger.remove()  # Remove default handler
logger.add(sys.stderr, level="INFO")  # Console output
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",  # Daily rotation
    retention="30 days",  # Keep for 30 days
    level="INFO"
)

# Global reference
log = logger

def setup_logger():
    """Setup logger with application-specific settings."""
    # Additional configuration if needed
    pass