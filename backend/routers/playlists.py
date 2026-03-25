"""
Playlists router — handles Spotify playlist submission and artist extraction.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Artist, Scandal
from schemas import PlaylistSubmit, PlaylistSubmitResponse, PlaylistArtist
from services.spotify import fetch_playlist
from errors import bad_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/playlists", tags=["Playlists"])


@router.post("/submit", response_model=PlaylistSubmitResponse)
async def submit_playlist(body: PlaylistSubmit, db: Session = Depends(get_db)):
    """
    Submit a Spotify playlist URL.
    Extracts all unique artists and stores them in the database.
    Skips artists that already exist (by spotify_id).
    """
    try:
        result = await fetch_playlist(body.playlist_url)
    except Exception:
        logger.exception("Failed to fetch playlist")
        bad_request("Failed to fetch playlist. Please check the URL and try again.")

    added = 0
    skipped = 0
    spotify_ids = []

    for artist_data in result["artists"]:
        spotify_ids.append(artist_data["spotify_id"])
        # Check if artist already exists
        existing = (
            db.query(Artist)
            .filter(Artist.spotify_id == artist_data["spotify_id"])
            .first()
        )
        if existing:
            skipped += 1
            continue

        # Create new artist record
        artist = Artist(
            name=artist_data["name"],
            spotify_id=artist_data["spotify_id"],
            image_url=artist_data.get("image_url"),
            approved=False,
        )
        db.add(artist)
        added += 1

    db.commit()

    # Fetch all playlist artists from DB with scandal counts
    artists_with_counts = (
        db.query(Artist, func.count(Scandal.id).label("scandal_count"))
        .outerjoin(Scandal, Scandal.artist_id == Artist.id)
        .filter(Artist.spotify_id.in_(spotify_ids))
        .group_by(Artist.id)
        .all()
    )
    playlist_artists = [
        PlaylistArtist(
            id=a.id,
            name=a.name,
            spotify_id=a.spotify_id,
            image_url=a.image_url,
            scandal_count=count,
        )
        for a, count in artists_with_counts
    ]

    return PlaylistSubmitResponse(
        playlist_name=result["playlist_name"],
        artists_added=added,
        artists_skipped=skipped,
        artists=playlist_artists,
    )
