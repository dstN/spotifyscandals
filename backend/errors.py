"""
Standardized HTTP error helpers.
Provides factory functions for common HTTPException patterns.
"""

from fastapi import HTTPException


def not_found(resource: str = "Resource") -> HTTPException:
    """Raise 404 with a standardized message."""
    raise HTTPException(status_code=404, detail=f"{resource} not found")


def bad_request(detail: str) -> HTTPException:
    """Raise 400 with a custom message."""
    raise HTTPException(status_code=400, detail=detail)


def conflict(detail: str) -> HTTPException:
    """Raise 409 with a custom message."""
    raise HTTPException(status_code=409, detail=detail)


def rate_limited(detail: str = "Rate limit exceeded. Try again later.") -> HTTPException:
    """Raise 429 with a rate-limit message."""
    raise HTTPException(status_code=429, detail=detail)


def internal_error(detail: str = "Internal server error") -> HTTPException:
    """Raise 500 with a generic message (never expose internals)."""
    raise HTTPException(status_code=500, detail=detail)
