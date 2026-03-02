"""
Artists router — CRUD and approval operations for artists.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import datetime, timezone, timedelta
from database import get_db
from models import Artist, Scandal, CommunityScandal
from schemas import ArtistResponse, ArtistDetail, CommunityScandalSubmit, CommunityScandalResponse
from auth_deps import require_admin, get_optional_public_user, get_current_public_user

router = APIRouter(prefix="/api/artists", tags=["Artists"])


@router.get("", response_model=list[ArtistResponse])
def list_artists(
    approved: bool | None = Query(None, description="Filter by approval status"),
    search: str | None = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
):
    """
    List all artists with optional filters.
    Includes scandal count for each artist.
    """
    query = db.query(Artist).options(joinedload(Artist.scandals).joinedload(Scandal.votes))

    if approved is not None:
        query = query.filter(Artist.approved == approved)

    if search:
        query = query.filter(Artist.name.ilike(f"%{search}%"))

    artists = query.order_by(Artist.created_at.desc()).all()

    # Build response with scandal counts and safety scores
    result = []
    for artist in artists:
        scandal_count = len(artist.scandals)
        
        # Calculate safety percentage logic
        total_votes = 0
        sum_votes = 0
        for s in artist.scandals:
            sum_votes += sum(v.vote_value for v in s.votes)
            total_votes += len(s.votes)
            
        safety_score = None
        if total_votes > 0:
            avg_vote = sum_votes / total_votes
            safety_score = ((10 - avg_vote) / 9) * 100

        result.append(ArtistResponse(
            id=artist.id,
            name=artist.name,
            spotify_id=artist.spotify_id,
            image_url=artist.image_url,
            approved=artist.approved,
            created_at=artist.created_at,
            scandal_count=scandal_count,
            safety_score=safety_score,
        ))

    return result


@router.get("/{artist_id}", response_model=ArtistDetail)
def get_artist(request: Request, artist_id: int, db: Session = Depends(get_db)):
    """Get a single artist with all their scandals, sources, and votes."""
    spotify_id = get_optional_public_user(request)

    artist = (
        db.query(Artist)
        .options(
            joinedload(Artist.scandals).joinedload(Scandal.sources),
            joinedload(Artist.scandals).joinedload(Scandal.votes)
        )
        .filter(Artist.id == artist_id)
        .first()
    )
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    scandal_count = len(artist.scandals)
    
    # Calculate safety percentage logic
    total_votes = 0
    sum_votes = 0
    scandals_response = []
    
    for s in artist.scandals:
        s_vote_count = len(s.votes)
        s_average_vote = sum(v.vote_value for v in s.votes) / s_vote_count if s_vote_count > 0 else None
        s_user_vote = next((v.vote_value for v in s.votes if v.spotify_user_id == spotify_id), None) if spotify_id else None
        
        sum_votes += sum(v.vote_value for v in s.votes)
        total_votes += s_vote_count
        
        scandals_response.append({
            "id": s.id,
            "artist_id": s.artist_id,
            "artist_name": artist.name,
            "description": s.description,
            "date_detected": s.date_detected,
            "verified": s.verified,
            "average_vote": s_average_vote,
            "vote_count": s_vote_count,
            "user_vote": s_user_vote,
            "sources": [
                {
                    "id": src.id, 
                    "source_url": src.source_url, 
                    "source_title": src.source_title,
                    "is_verified": src.is_verified,
                    "is_reported": src.is_reported,
                    "created_at": src.created_at
                }
                for src in s.sources
            ],
        })
        
    safety_score = None
    if total_votes > 0:
        avg_vote = sum_votes / total_votes
        safety_score = ((10 - avg_vote) / 9) * 100

    # Fetch community scandals
    comm_scandals = db.query(CommunityScandal).filter(CommunityScandal.artist_id == artist_id).order_by(CommunityScandal.created_at.desc()).all()

    return ArtistDetail(
        id=artist.id,
        name=artist.name,
        spotify_id=artist.spotify_id,
        image_url=artist.image_url,
        approved=artist.approved,
        created_at=artist.created_at,
        scandal_count=scandal_count,
        safety_score=safety_score,
        scandals=scandals_response,
        community_scandals=comm_scandals,
    )


@router.patch("/{artist_id}/approve")
def approve_artist(artist_id: int, db: Session = Depends(get_db), admin: str = Depends(require_admin)):
    """Toggle artist approval status."""
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    artist.approved = not artist.approved
    db.commit()
    db.refresh(artist)

    return {"id": artist.id, "name": artist.name, "approved": artist.approved}


@router.post("/approve-all")
def approve_all_artists(db: Session = Depends(get_db), admin: str = Depends(require_admin)):
    """Approve all pending artists."""
    pending_artists = db.query(Artist).filter(Artist.approved == False).all()
    count = len(pending_artists)
    
    for artist in pending_artists:
        artist.approved = True
        
    db.commit()
    return {"message": f"Successfully approved {count} artists", "count": count}


@router.delete("/{artist_id}")
def delete_artist(artist_id: int, db: Session = Depends(get_db), admin: str = Depends(require_admin)):
    """Delete an artist and all associated scandals (cascade)."""
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    db.delete(artist)
    db.commit()
    return {"detail": f"Artist '{artist.name}' deleted"}

@router.post("/{artist_id}/community-scandals", response_model=CommunityScandalResponse)
def submit_community_scandal(
    artist_id: int, 
    body: CommunityScandalSubmit, 
    db: Session = Depends(get_db), 
    spotify_id: str = Depends(get_current_public_user)
):
    """Submit a community scandal suggestion, requires Spotify Auth."""
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
        
    # Rate limit check: max 3 per hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_count = db.query(CommunityScandal).filter(
        CommunityScandal.spotify_user_id == spotify_id,
        CommunityScandal.created_at >= one_hour_ago
    ).count()
    if recent_count >= 3:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. You can only submit 3 scandals per hour.")
        
    scandal = CommunityScandal(
        artist_id=artist_id,
        spotify_user_id=spotify_id,
        title=body.title,
        description=body.description,
        source_url=body.source_url
    )
    db.add(scandal)
    db.commit()
    db.refresh(scandal)
    return scandal
