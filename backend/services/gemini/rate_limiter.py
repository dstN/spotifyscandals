"""
In-memory rate limiter for Gemini API calls.
Tracks per-minute and per-day counters for model and search calls.
"""

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone

from config import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Process-level rate limiter for Gemini API calls.
    Tracks per-minute and per-day counters for model and search calls.
    In free_tier mode, blocks when limits are approached; in unlimited mode, only throttles RPM.
    """

    def __init__(self):
        settings = get_settings()
        self.mode = settings.scanner_mode.lower()
        self.model_rpm = settings.gemini_model_rpm
        self.model_rpd = settings.gemini_model_rpd
        self.search_rpd = settings.gemini_search_rpd

        # Per-minute sliding window (timestamps of recent model calls)
        self._minute_window: deque[float] = deque()
        # Daily counters (reset on first call each new UTC day)
        self._day_key: str = ""
        self._model_day_count: int = 0
        self._search_day_count: int = 0
        self._lock = asyncio.Lock()

    def _reset_day_if_needed(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._day_key:
            self._day_key = today
            self._model_day_count = 0
            self._search_day_count = 0

    def _prune_minute_window(self):
        now = time.monotonic()
        while self._minute_window and (now - self._minute_window[0]) > 60:
            self._minute_window.popleft()

    async def acquire(self, uses_search: bool = False):
        """
        Wait until a request slot is available, then record the call.
        Raises RuntimeError if daily limit is exhausted in free_tier mode.
        """
        async with self._lock:
            self._reset_day_if_needed()

            if self.mode == "free_tier":
                # Check daily model limit
                if self._model_day_count >= self.model_rpd:
                    raise RuntimeError(
                        f"Daily model request limit reached ({self.model_rpd} RPD). "
                        "Scan paused — try again tomorrow or switch to unlimited mode."
                    )
                # Check daily search limit
                if uses_search and self._search_day_count >= self.search_rpd:
                    raise RuntimeError(
                        f"Daily search grounding limit reached ({self.search_rpd} RPD). "
                        "Scan paused — try again tomorrow or switch to unlimited mode."
                    )

            # RPM throttle (applies in all modes)
            self._prune_minute_window()
            if len(self._minute_window) >= self.model_rpm:
                wait = 60 - (time.monotonic() - self._minute_window[0]) + 0.5
                if wait > 0:
                    logger.info("RPM limit (%s/min) reached — waiting %.1fs", self.model_rpm, wait)
                    # Release lock while sleeping so other tasks aren't blocked
                    self._lock.release()
                    try:
                        await asyncio.sleep(wait)
                    finally:
                        await self._lock.acquire()
                    self._prune_minute_window()

            # Record the call
            self._minute_window.append(time.monotonic())
            self._model_day_count += 1
            if uses_search:
                self._search_day_count += 1

    @property
    def stats(self) -> dict:
        self._reset_day_if_needed()
        self._prune_minute_window()
        return {
            "mode": self.mode,
            "model_rpm_used": len(self._minute_window),
            "model_rpm_limit": self.model_rpm,
            "model_rpd_used": self._model_day_count,
            "model_rpd_limit": self.model_rpd,
            "search_rpd_used": self._search_day_count,
            "search_rpd_limit": self.search_rpd,
        }


# Singleton rate limiter instance (per-process)
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
