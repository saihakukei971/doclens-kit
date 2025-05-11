# app/core/security.py
from fastapi import Request, HTTPException, Depends
from fastapi.security import APIKeyHeader
from app.core.config import settings
from app.core.logger import log
import os
import ipaddress
import hashlib
import secrets
import time
from typing import List, Optional, Union

# Simple IP-based access control
def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    elif request.client:
        return request.client.host
    return "0.0.0.0"

def is_ip_allowed(ip: str) -> bool:
    """Check if IP is allowed to access the system."""
    # If no restriction defined, allow all
    if not hasattr(settings, "ALLOWED_IPS") or not settings.ALLOWED_IPS:
        return True

    # Check against allowed IPs/networks
    client_ip = ipaddress.ip_address(ip)
    for allowed_ip in settings.ALLOWED_IPS:
        # Check if it's a network range
        if "/" in allowed_ip:
            network = ipaddress.ip_network(allowed_ip, strict=False)
            if client_ip in network:
                return True
        # Check exact IP match
        elif ipaddress.ip_address(allowed_ip) == client_ip:
            return True

    return False

# Simple API key authentication
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key."""
    if not hasattr(settings, "API_KEYS") or not settings.API_KEYS:
        # No API keys defined, skipping check
        return True

    if not api_key or api_key not in settings.API_KEYS:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API key",
        )
    return True

# IP restriction middleware
async def ip_filter_middleware(request: Request, call_next):
    """Middleware to filter requests by IP address."""
    client_ip = get_client_ip(request)

    if not is_ip_allowed(client_ip):
        log.warning(f"アクセス拒否: 不許可IP {client_ip}")
        return HTTPException(status_code=403, detail="Access denied")

    # Continue with the request
    response = await call_next(request)
    return response

# Generate secure random token
def generate_token(length: int = 32) -> str:
    """Generate a secure random token."""
    return secrets.token_hex(length // 2)

# Hash password
def hash_password(password: str) -> str:
    """Hash a password for storing."""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    )
    return salt.hex() + '$' + key.hex()

# Verify password
def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verify a stored password against a provided password."""
    salt_hex, key_hex = stored_password.split('$')
    salt = bytes.fromhex(salt_hex)
    stored_key = bytes.fromhex(key_hex)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        provided_password.encode('utf-8'),
        salt,
        100000
    )
    return secrets.compare_digest(key, stored_key)

# Rate limiting
class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, rate_limit: int = 60, time_frame: int = 60):
        """
        Initialize rate limiter.

        Args:
            rate_limit: Maximum number of requests
            time_frame: Time frame in seconds
        """
        self.rate_limit = rate_limit
        self.time_frame = time_frame
        self.requests = {}  # IP -> list of timestamps

    def is_rate_limited(self, ip: str) -> bool:
        """
        Check if IP is rate limited.

        Args:
            ip: IP address

        Returns:
            True if rate limited, False otherwise
        """
        now = time.time()

        # Initialize empty list for new IP
        if ip not in self.requests:
            self.requests[ip] = []

        # Remove old timestamps
        self.requests[ip] = [ts for ts in self.requests[ip] if now - ts < self.time_frame]

        # Check rate limit
        if len(self.requests[ip]) >= self.rate_limit:
            return True

        # Add current timestamp
        self.requests[ip].append(now)
        return False

# Create rate limiter instance
rate_limiter = RateLimiter()

# Access log
def log_access(request: Request, status_code: int, processing_time: float):
    """Log access information."""
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")
    method = request.method
    url = str(request.url)

    log.info(f"アクセス: {client_ip} {method} {url} {status_code} {processing_time:.3f}s {user_agent}")