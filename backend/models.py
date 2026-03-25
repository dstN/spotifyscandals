"""
SQLAlchemy ORM models for the Skandal Tracker database.

Tables:
  - artists:         Spotify artists extracted from playlists
  - scandals:        Detected scandals linked to artists
  - scandal_sources: URLs backing each scandal claim
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from database import Base


class Artist(Base):
    """
    An artist extracted from a Spotify playlist.
    Must be approved by an admin before scandal scanning.
    """
    __tablename__ = "artists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    spotify_id = Column(String(255), unique=True, nullable=False, index=True)
    image_url = Column(Text, nullable=True)
    approved = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    last_scanned_at = Column(DateTime, nullable=True)

    # One-to-many: an artist can have multiple scandals
    scandals = relationship(
        "Scandal", back_populates="artist", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Artist(id={self.id}, name='{self.name}', approved={self.approved})>"


class Scandal(Base):
    """
    A scandal detected for an artist via Gemini Pro.
    Must be verified by an admin after review.
    """
    __tablename__ = "scandals"

    id = Column(Integer, primary_key=True, index=True)
    artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=False)
    date_detected = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    verified = Column(Boolean, default=False, nullable=False)
    is_community = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    artist = relationship("Artist", back_populates="scandals")
    sources = relationship(
        "ScandalSource", back_populates="scandal", cascade="all, delete-orphan"
    )
    votes = relationship(
        "ScandalVote", back_populates="scandal", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Scandal(id={self.id}, artist_id={self.artist_id}, verified={self.verified})>"


class ScandalSource(Base):
    """
    A source URL that backs a scandal claim.
    Linked to a specific scandal record.
    """
    __tablename__ = "scandal_sources"

    id = Column(Integer, primary_key=True, index=True)
    scandal_id = Column(
        Integer, ForeignKey("scandals.id", ondelete="CASCADE"), nullable=False
    )
    source_url = Column(Text, nullable=False)
    source_title = Column(String(255), nullable=True)  # Human-readable site name from grounding metadata
    is_reported = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationship back to parent scandal
    scandal = relationship("Scandal", back_populates="sources")

    def __repr__(self):
        return f"<ScandalSource(id={self.id}, url='{self.source_url[:50]}...')>"


class ScandalVote(Base):
    """
    User vote (1-10) on how severe a scandal is.
    Logged via Spotify OAuth ID to prevent duplicate votes.
    """
    __tablename__ = "scandal_votings"

    id = Column(Integer, primary_key=True, index=True)
    scandal_id = Column(
        Integer, ForeignKey("scandals.id", ondelete="CASCADE"), nullable=False
    )
    spotify_user_id = Column(String(255), nullable=False, index=True)
    vote_value = Column(Integer, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationship back to parent scandal
    scandal = relationship("Scandal", back_populates="votes")

    def __repr__(self):
        return f"<ScandalVote(id={self.id}, scandal_id={self.scandal_id}, vote={self.vote_value})>"


class CommunityScandal(Base):
    """
    Scandal details submitted by the public community.
    Waiting for admin review.
    """
    __tablename__ = "community_scandals"

    id = Column(Integer, primary_key=True, index=True)
    artist_id = Column(
        Integer, ForeignKey("artists.id", ondelete="CASCADE"), nullable=False
    )
    spotify_user_id = Column(String(255), nullable=False, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    source_url = Column(Text, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationship back to parent artist
    artist = relationship("Artist")

    def __repr__(self):
        return f"<CommunityScandal(id={self.id}, artist_id={self.artist_id}, spotify_user_id='{self.spotify_user_id}')>"


class CommunitySource(Base):
    """
    A source URL submitted by the public community for an existing scandal.
    Waiting for admin review before being added as a verified ScandalSource.
    """
    __tablename__ = "community_sources"

    id = Column(Integer, primary_key=True, index=True)
    scandal_id = Column(
        Integer, ForeignKey("scandals.id", ondelete="CASCADE"), nullable=False
    )
    spotify_user_id = Column(String(255), nullable=False, index=True)
    source_url = Column(Text, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    scandal = relationship("Scandal")

    def __repr__(self):
        return f"<CommunitySource(id={self.id}, scandal_id={self.scandal_id})>"


class BatchJob(Base):
    """
    Tracks a Gemini Batch API job submitted for background scanning.
    """
    __tablename__ = "batch_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_name = Column(String(500), unique=True, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, RUNNING, SUCCEEDED, FAILED, CANCELLED, EXPIRED
    artist_ids_json = Column(Text, nullable=False)  # JSON array of artist IDs included in this batch
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<BatchJob(id={self.id}, job_name='{self.job_name}', status='{self.status}')>"
