"""
Pydantic schemas for request validation and response serialization.
Separates API contract from database models.
"""

from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import Optional


# ═══════════════════════════════════════════
#  Playlist Schemas
# ═══════════════════════════════════════════

class PlaylistSubmit(BaseModel):
    """Request body for submitting a Spotify playlist URL."""
    playlist_url: str = Field(..., min_length=10, max_length=1024)


class PlaylistArtist(BaseModel):
    """Lightweight artist info returned after playlist extraction."""
    id: int
    name: str
    spotify_id: str
    image_url: Optional[str] = None
    scandal_count: int = 0

    class Config:
        from_attributes = True


class PlaylistSubmitResponse(BaseModel):
    """Response after extracting artists from a playlist."""
    playlist_name: str
    artists_added: int
    artists_skipped: int  # Already existed in DB
    artists: list[PlaylistArtist] = []


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
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    source_url: Optional[str] = Field(None, max_length=2048)


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
    vote: int = Field(..., ge=0, le=10)


class AdminSourceCreate(BaseModel):
    """Request body for admin directly adding a source to a scandal."""
    source_url: str = Field(..., min_length=10, max_length=2048)


class CommunitySourceSubmit(BaseModel):
    """Request body for a public user submitting a source for an existing scandal."""
    source_url: str = Field(..., min_length=10, max_length=2048)


class ExistingSourceBrief(BaseModel):
    """Brief source info for showing existing sources alongside a pending community source."""
    id: int
    source_url: str
    source_title: Optional[str] = None

    class Config:
        from_attributes = True


class CommunitySourceResponse(BaseModel):
    """Community submitted source waiting for review."""
    id: int
    scandal_id: int
    spotify_user_id: str
    source_url: str
    created_at: datetime
    scandal_title: Optional[str] = None
    scandal_description: Optional[str] = None
    artist_name: Optional[str] = None
    artist_image_url: Optional[str] = None
    existing_sources: list[ExistingSourceBrief] = []

    class Config:
        from_attributes = True


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


# ═══════════════════════════════════════════
#  Generic Response Schemas
# ═══════════════════════════════════════════

class MessageResponse(BaseModel):
    """Generic message-only response."""
    message: Optional[str] = None
    detail: Optional[str] = None


class VoteResponse(BaseModel):
    """Response after recording a vote."""
    message: str
    user_vote: int
    average_vote: float
    vote_count: int


class VerifyToggleResponse(BaseModel):
    """Response after toggling verification status."""
    id: int
    verified: bool


class SourceVerifyToggleResponse(BaseModel):
    """Response after toggling source verification status."""
    id: int
    is_verified: bool


class SourceCreatedResponse(BaseModel):
    """Response after creating a source."""
    id: int
    source_url: str
    is_verified: bool


class ArtistApproveResponse(BaseModel):
    """Response after toggling artist approval."""
    id: int
    name: str
    approved: bool


class MessageCountResponse(BaseModel):
    """Response with a message and a count."""
    message: str
    count: int


class PendingCountResponse(BaseModel):
    """Pending community items count."""
    scandals: int
    sources: int
    total: int


class ReportResponse(BaseModel):
    """Response after reporting a source."""
    message: str
    is_reported: bool
