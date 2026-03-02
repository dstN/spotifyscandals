"""
Pydantic schemas for request validation and response serialization.
Separates API contract from database models.
"""

from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Optional


# ═══════════════════════════════════════════
#  Playlist Schemas
# ═══════════════════════════════════════════

class PlaylistSubmit(BaseModel):
    """Request body for submitting a Spotify playlist URL."""
    playlist_url: str


class PlaylistSubmitResponse(BaseModel):
    """Response after extracting artists from a playlist."""
    playlist_name: str
    artists_added: int
    artists_skipped: int  # Already existed in DB


# ═══════════════════════════════════════════
#  Artist Schemas
# ═══════════════════════════════════════════

class ArtistBase(BaseModel):
    name: str
    spotify_id: str
    image_url: Optional[str] = None

class ArtistResponse(ArtistBase):
    """Full artist response including DB metadata."""
    id: int
    approved: bool
    created_at: datetime
    scandal_count: int = 0
    safety_score: Optional[float] = None

    class Config:
        from_attributes = True


class ArtistDetail(ArtistResponse):
    """Artist with nested scandals for detail view."""
    scandals: list["ScandalResponse"] = []


# ═══════════════════════════════════════════
#  Scandal Schemas
# ═══════════════════════════════════════════

class ScandalSourceResponse(BaseModel):
    """A source URL backing a scandal."""
    id: int
    source_url: str
    source_title: Optional[str] = None
    is_reported: bool = False
    is_verified: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ScandalResponse(BaseModel):
    """Scandal with sources and artist name."""
    id: int
    artist_id: int
    artist_name: str = ""
    artist_image_url: str | None = None
    title: str = ""
    description: str
    date_detected: datetime
    verified: bool
    is_community: bool = False
    average_vote: Optional[float] = None
    vote_count: int = 0
    user_vote: Optional[int] = None
    sources: list[ScandalSourceResponse] = []

    class Config:
        from_attributes = True


class CommunityScandalSubmit(BaseModel):
    """Request body for a public user submitting a missed scandal."""
    title: str
    description: str
    source_url: Optional[str] = None


class CommunityScandalResponse(BaseModel):
    """Community submitted scandal waiting for review."""
    id: int
    artist_id: int
    spotify_user_id: str
    title: str
    description: str
    source_url: Optional[str] = None
    created_at: datetime
    artist: Optional["ArtistResponse"] = None

    class Config:
        from_attributes = True


class VoteRequest(BaseModel):
    """Request body for submitting a vote on a scandal."""
    vote: int  # 1 to 10


class ScanScandalRequest(BaseModel):
    """Request body for scanning specific artists (or all approved)."""
    artist_ids: list[int] = []  # Empty = scan all approved


class ScanScandalResponse(BaseModel):
    """Response after a Gemini Pro scandal scan."""
    artists_scanned: int
    scandals_found: int


# ═══════════════════════════════════════════
#  Stats Schema
# ═══════════════════════════════════════════

class DashboardStats(BaseModel):
    """Aggregate stats for the dashboard."""
    total_artists: int
    approved_artists: int
    pending_artists: int
    total_scandals: int
    verified_scandals: int
    unverified_scandals: int
