"""
Google Gemini integration service — scandal scanning, source evaluation, and batch API.

This package provides backwards-compatible imports for all public functions.
"""

# Rate limiting
from .rate_limiter import RateLimiter, get_rate_limiter

# URL resolution & filtering
from .url_resolver import (
    BLOCKED_SOURCE_DOMAINS,
    is_blocked_domain,
    is_internal_url,
    resolve_url as _resolve_url,
    resolve_url_deep as _resolve_url_deep,
    resolve_url_ultra as _resolve_url_ultra,
)

# Source-to-scandal attribution
from .source_matcher import match_sources_to_scandals as _match_sources_to_scandals

# Core scanning
from .scanner import (
    scan_artist_for_scandals,
    scan_artists_for_scandals,
)

# Source evaluation
from .evaluator import (
    verify_source_relevance,
    score_source_relevance,
    find_better_sources,
)

# Batch API
from .batch import (
    create_batch_requests,
    submit_batch_job,
    poll_batch_job,
    parse_batch_response,
)

__all__ = [
    # Rate limiting
    "RateLimiter",
    "get_rate_limiter",
    # URL resolution
    "BLOCKED_SOURCE_DOMAINS",
    "is_blocked_domain",
    "is_internal_url",
    "_resolve_url",
    "_resolve_url_deep",
    "_resolve_url_ultra",
    # Source matching
    "_match_sources_to_scandals",
    # Scanner
    "scan_artist_for_scandals",
    "scan_artists_for_scandals",
    # Evaluator
    "verify_source_relevance",
    "score_source_relevance",
    "find_better_sources",
    # Batch
    "create_batch_requests",
    "submit_batch_job",
    "poll_batch_job",
    "parse_batch_response",
]
