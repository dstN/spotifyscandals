"""
Scandals router — listing, Gemini scanning, and verification.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from database import get_db
from models import Artist, Scandal, ScandalSource, ScandalVote
from schemas import (
    ScandalResponse,
    ScanScandalRequest,
    ScanScandalResponse,
    DashboardStats,
    VoteRequest,
)
from services.gemini import scan_artists_for_scandals
from auth_deps import require_admin, get_current_public_user, get_optional_public_user

router = APIRouter(prefix="/api/scandals", tags=["Scandals"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)):
    """Dashboard statistics: artist and scandal counts."""
    total_artists = db.query(func.count(Artist.id)).scalar()
    approved_artists = db.query(func.count(Artist.id)).filter(Artist.approved == True).scalar()  # noqa
    total_scandals = db.query(func.count(Scandal.id)).scalar()
    verified_scandals = db.query(func.count(Scandal.id)).filter(Scandal.verified == True).scalar()  # noqa

    return DashboardStats(
        total_artists=total_artists,
        approved_artists=approved_artists,
        pending_artists=total_artists - approved_artists,
        total_scandals=total_scandals,
        verified_scandals=verified_scandals,
        unverified_scandals=total_scandals - verified_scandals,
    )


@router.get("", response_model=list[ScandalResponse])
def list_scandals(
    request: Request,
    verified: bool | None = Query(None, description="Filter by verification status"),
    artist_id: int | None = Query(None, description="Filter by artist"),
    db: Session = Depends(get_db),
):
    """List all scandals with optional filters."""
    spotify_id = get_optional_public_user(request)

    query = db.query(Scandal).options(
        joinedload(Scandal.sources), 
        joinedload(Scandal.artist),
        joinedload(Scandal.votes)
    )

    if verified is not None:
        query = query.filter(Scandal.verified == verified)
    if artist_id is not None:
        query = query.filter(Scandal.artist_id == artist_id)

    scandals = query.order_by(Scandal.date_detected.desc()).all()

    response = []
    for s in scandals:
        vote_count = len(s.votes)
        average_vote = sum(v.vote_value for v in s.votes) / vote_count if vote_count > 0 else None
        user_vote = next((v.vote_value for v in s.votes if v.spotify_user_id == spotify_id), None) if spotify_id else None
        
        response.append(
            ScandalResponse(
                id=s.id,
                artist_id=s.artist_id,
                artist_name=s.artist.name if s.artist else "Unknown",
                artist_image_url=s.artist.image_url if s.artist else None,
                title=s.title or "",
                description=s.description,
                date_detected=s.date_detected,
                verified=s.verified,
                is_community=s.is_community,
                average_vote=average_vote,
                vote_count=vote_count,
                user_vote=user_vote,
                sources=[
                    {"id": src.id, "source_url": src.source_url, "source_title": src.source_title, "created_at": src.created_at}
                    for src in s.sources
                ],
            )
        )
        
    return response

@router.post("/{scandal_id}/vote")
def submit_scandal_vote(
    scandal_id: int, 
    body: VoteRequest, 
    db: Session = Depends(get_db), 
    spotify_id: str = Depends(get_current_public_user)
):
    """Allow a public authenticated user to vote (1-10) on a scandal's severity."""
    scandal = db.query(Scandal).filter(Scandal.id == scandal_id).first()
    if not scandal:
        raise HTTPException(status_code=404, detail="Scandal not found")
        
    if not (1 <= body.vote <= 10):
        raise HTTPException(status_code=400, detail="Vote must be between 1 and 10")
        
    vote_record = db.query(ScandalVote).filter(
        ScandalVote.scandal_id == scandal_id,
        ScandalVote.spotify_user_id == spotify_id
    ).first()
    
    if vote_record:
        vote_record.vote_value = body.vote
    else:
        vote_record = ScandalVote(
            scandal_id=scandal_id,
            spotify_user_id=spotify_id,
            vote_value=body.vote
        )
        db.add(vote_record)
        
    db.commit()
    
    # Return updated average
    votes = db.query(ScandalVote).filter(ScandalVote.scandal_id == scandal_id).all()
    avg = sum(v.vote_value for v in votes) / len(votes)
    
    return {
        "message": "Vote recorded successfully", 
        "user_vote": body.vote,
        "average_vote": avg,
        "vote_count": len(votes)
    }


from database import SessionLocal
import asyncio

from datetime import datetime, timezone, timedelta

async def _process_scan_background(artist_data: list[dict]):
    """Background task to call Gemini and save results to the database."""
    try:
        results = await scan_artists_for_scandals(artist_data)
        
        # We need a new DB session for the background task
        # since the request's Depends(get_db) session will already be closed
        db = SessionLocal()
        try:
            for artist_result in results:
                artist_id = artist_result.get("artist_id")
                
                # Update last scanned time
                db_artist = db.query(Artist).filter(Artist.id == artist_id).first()
                if db_artist:
                    db_artist.last_scanned_at = datetime.now(timezone.utc)

                for scandal_data in artist_result.get("scandals", []):
                    description = scandal_data.get("description", "").strip()
                    if not description:
                        continue

                    existing = (
                        db.query(Scandal)
                        .filter(
                            Scandal.artist_id == artist_id,
                            Scandal.description == description,
                        )
                        .first()
                    )
                    if existing:
                        continue

                    scandal = Scandal(
                        artist_id=artist_id,
                        title=scandal_data.get("title", "").strip(),
                        description=description,
                        verified=False,
                    )
                    db.add(scandal)
                    db.flush()

                    for source_item in scandal_data.get("sources", []):
                        # sources is now a list of {"url": ..., "title": ...} dicts
                        if isinstance(source_item, dict):
                            url = source_item.get("url", "").strip()
                            title = source_item.get("title", None)
                        else:
                            # fallback: plain string
                            url = str(source_item).strip()
                            title = None
                        if url:
                            source = ScandalSource(
                                scandal_id=scandal.id,
                                source_url=url,
                                source_title=title,
                            )
                            db.add(source)

            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"Background scan failed: {e}")

@router.post("/scan")
async def scan_for_scandals(
    body: ScanScandalRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db), 
    admin: str = Depends(require_admin)
):
    """
    Scan approved artists for scandals using Google Gemini Pro.
    Executes the scan in the background so the API doesn't block.
    """
    if body.artist_ids:
        artists = db.query(Artist).options(joinedload(Artist.scandals)).filter(Artist.id.in_(body.artist_ids), Artist.approved == True).all()  # noqa
    else:
        artists = db.query(Artist).options(joinedload(Artist.scandals)).filter(Artist.approved == True).all()  # noqa

    if not artists:
        raise HTTPException(status_code=404, detail="No approved artists found to scan")

    four_weeks_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(weeks=4)
    artists_to_scan = []
    
    for a in artists:
        last_scan = a.last_scanned_at
        if last_scan:
            last_scan = last_scan.replace(tzinfo=None)
            
        if last_scan is None or last_scan < four_weeks_ago:
            artists_to_scan.append(a)

    if not artists_to_scan:
        return {"message": "All assigned artists have been scanned within the last 4 weeks. Nothing to do."}

    artist_data = []
    for a in artists_to_scan:
        existing_scandals = [{"title": s.title, "description": s.description} for s in a.scandals]
        artist_data.append({
            "id": a.id, 
            "name": a.name, 
            "spotify_id": a.spotify_id,
            "existing_scandals": existing_scandals
        })

    # Queue the background task
    background_tasks.add_task(_process_scan_background, artist_data)

    return {"message": f"Scan initiated for {len(artists_to_scan)} artists in the background. Check back later for results."}


@router.patch("/{scandal_id}/verify")
def verify_scandal(scandal_id: int, db: Session = Depends(get_db), admin: str = Depends(require_admin)):
    """Toggle scandal verification status."""
    scandal = db.query(Scandal).filter(Scandal.id == scandal_id).first()
    if not scandal:
        raise HTTPException(status_code=404, detail="Scandal not found")

    scandal.verified = not scandal.verified
    db.commit()
    db.refresh(scandal)

    return {"id": scandal.id, "verified": scandal.verified}


@router.delete("/{scandal_id}")
def delete_scandal(scandal_id: int, db: Session = Depends(get_db), admin: str = Depends(require_admin)):
    """Delete a scandal and its sources (cascade)."""
    scandal = db.query(Scandal).filter(Scandal.id == scandal_id).first()
    if not scandal:
        raise HTTPException(status_code=404, detail="Scandal not found")

    db.delete(scandal)
    db.commit()
    return {"detail": "Scandal deleted"}


@router.delete("/{scandal_id}/sources/{source_id}")
def delete_scandal_source(
    scandal_id: int, 
    source_id: int, 
    db: Session = Depends(get_db), 
    admin: str = Depends(require_admin)
):
    """Delete a specific source from a scandal."""
    source = db.query(ScandalSource).filter(
        ScandalSource.id == source_id,
        ScandalSource.scandal_id == scandal_id
    ).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    db.delete(source)
    db.commit()
    return {"detail": "Source deleted"}
