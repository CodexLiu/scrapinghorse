"""
Rate Limiting Module for Scraping Horse Gateway

This module provides comprehensive rate limiting functionality using slowapi.
It supports different rate limits for different types of endpoints and can
identify users by IP address and API key for more granular control.

Environment Variables:
- RATE_LIMIT_DEFAULT: Default rate limit (default: "100/minute")
- RATE_LIMIT_STORAGE_URI: Storage backend URI (default: "memory://")

Usage:
    # In route handlers:
    @limiter.limit(RateLimits.SEARCH)
    async def search(request: Request, ...):
        ...

Rate Limit Tiers:
- GENERAL: 100/minute - General API usage
- SEARCH: 30/minute - Expensive search operations  
- SENSITIVE: 10/minute - Sensitive operations
- PUBLIC: 50/minute - Public endpoints (no auth)
"""

import os
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware


def get_rate_limit_key(request: Request) -> str:
    """
    Generate rate limit key based on client IP and API key if available.
    This allows for more granular rate limiting.
    """
    # Get client IP
    KEY_ID_LENGTH = 8
    client_ip = get_remote_address(request)
    
    # Try to get API key from headers for more granular limiting
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Use last KEY_ID_LENGTH characters of API key + IP for identification
        return f"{api_key[-KEY_ID_LENGTH:]}:{client_ip}"
    
    return client_ip


def create_limiter() -> Limiter:
    """
    Create and configure the rate limiter instance.
    """
    # Get rate limit configuration from environment
    default_rate_limit = os.getenv("RATE_LIMIT_DEFAULT", "100/minute")
    
    return Limiter(
        key_func=get_rate_limit_key,
        default_limits=[default_rate_limit],
        storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
        strategy="fixed-window",  # or "moving-window" for more accurate limiting
    )


# Create global limiter instance
limiter = create_limiter()


def setup_rate_limiting(app: FastAPI, limiter_instance: Optional[Limiter] = None):
    """
    Setup rate limiting middleware and error handlers for FastAPI app.
    
    Args:
        app: FastAPI application instance
        limiter_instance: Optional custom limiter instance
    """
    if limiter_instance is None:
        limiter_instance = limiter
    
    # Attach limiter to app state (required by SlowAPI middleware)
    app.state.limiter = limiter_instance
    
    # Add rate limiting middleware
    app.add_middleware(SlowAPIMiddleware)
    
    # Add rate limit exceeded handler
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    return limiter_instance


# Rate limiting decorators for different endpoints
class RateLimits:
    """Common rate limit configurations"""
    
    # Generous limits for general API usage
    GENERAL = "100/minute"
    
    # More restrictive for expensive operations like search
    SEARCH = "30/minute"
    
    # Very restrictive for sensitive operations
    SENSITIVE = "10/minute"
    
    # Public endpoints (no auth required)
    PUBLIC = "50/minute"


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom rate limit exceeded handler with detailed error information.
    """
    return HTTPException(
        status_code=429,
        detail={
            "error": "Rate limit exceeded",
            "message": f"Too many requests. Limit: {exc.detail}",
            "retry_after": exc.retry_after,
            "limit": str(exc.detail),
        },
        headers={"Retry-After": str(exc.retry_after)} if exc.retry_after else None,
    )
