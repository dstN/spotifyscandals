"""
Playlists router — handles Spotify playlist submission and artist extraction.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Artist
from schemas import PlaylistSubmit, PlaylistSubmitResponse
from services.spotify import fetch_playlist

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
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch playlist: {str(e)}"
        )

    added = 0
    skipped = 0

    for artist_data in result["artists"]:
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

    return PlaylistSubmitResponse(
        playlist_name=result["playlist_name"],
        artists_added=added,
        artists_skipped=skipped,
    )
