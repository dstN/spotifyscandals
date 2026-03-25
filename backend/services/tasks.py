"""
Background tasks — auto-scan top artists (DISABLED).

NOTE: Spotify's curated playlists (Top 50 Global, Viral 50, etc.) are NOT
accessible via the Client Credentials OAuth flow — they require user authentication.

Auto-scan is disabled. Use manual workflow instead:
  1. Submit your own playlist URL
  2. Admin approves extracted artists
  3. Trigger scan from admin dashboard

Trending/top artist scanning requires Spotify's user-level APIs or an alternative
music data source.
"""

import logging
import os
import sys
import json
import tempfile
import subprocess
from datetime import datetime, timezone, timedelta

from database import SessionLocal
from models import Artist, Scandal
from services.spotify import fetch_playlist

logger = logging.getLogger(__name__)


async def run_top50_auto_scan():
    """
    Auto-scan is disabled (Spotify curated playlists require user authentication).
    Use manual playlist submission workflow instead.
    """
    logger.info("Auto-scan disabled (Spotify curated playlists not accessible via Client Credentials). Use manual playlist submission.")
    return
