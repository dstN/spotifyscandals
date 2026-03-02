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
    reported: bool | None = Query(None, description="Filter by reported status"),
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
    if reported is True:
        query = query.filter(Scandal.sources.any(ScandalSource.is_reported == True))
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
                    {
                        "id": src.id, 
                        "source_url": src.source_url, 
                        "source_title": src.source_title, 
                        "is_reported": src.is_reported,
                        "is_verified": src.is_verified,
                        "created_at": src.created_at
                    }
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
import subprocess
import tempfile
import sys
import os
import json
from datetime import datetime, timezone, timedelta

def _trigger_detached_scan(artist_data: list[dict]):
    """Launch the scanner_cli.py as a detached process."""
    # Create a temporary file to pass the data
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        json.dump(artist_data, tmp)
        tmp_path = tmp.name

    # Path to the scanner_cli.py (relative to backend)
    # Get current file's directory (backend/routers/scandals.py)
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cli_path = os.path.join(backend_dir, "scanner_cli.py")
    python_exe = sys.executable

    # Launch detached process
    # creationflags for Windows to ensure it survives
    creationflags = 0
    if sys.platform == "win32":
        # CREATE_NEW_PROCESS_GROUP ensures it runs independently
        # DETACHED_PROCESS ensures it has no console (optional but good for background)
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    try:
        # We no longer redirect OS-level stdout here so the user can see it in their terminal.
        # Instead, scanner_cli.py will duplicate its own output to the log file.
        subprocess.Popen(
            [python_exe, cli_path, tmp_path],
            cwd=backend_dir,
            creationflags=creationflags,
            start_new_session=True if sys.platform != "win32" else False
        )
        print(f"[Scandal-Router] Detached scan process started. UI Logs enabled.")
    except Exception as e:
        print(f"[Scandal-Router] Failed to launch detached scan: {e}")
        # Cleanup temp file if launch failed
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

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

    # Trigger the detached scan process
    # Check if a scan is already running to avoid conflicts
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lock_path = os.path.join(backend_dir, "scan.lock")
    if os.path.exists(lock_path):
        raise HTTPException(status_code=400, detail="A scan is already in progress. Please wait for it to finish.")

    _trigger_detached_scan(artist_data)

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
@router.patch("/{scandal_id}/sources/{source_id}/verify")
def verify_scandal_source(
    scandal_id: int, 
    source_id: int, 
    db: Session = Depends(get_db), 
    admin: str = Depends(require_admin)
):
    """Toggle the verification status of a specific source."""
    source = db.query(ScandalSource).filter(
        ScandalSource.id == source_id,
        ScandalSource.scandal_id == scandal_id
    ).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    source.is_verified = not source.is_verified
    db.commit()
    db.refresh(source)
    
    return {"id": source.id, "is_verified": source.is_verified}


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


@router.post("/{scandal_id}/sources/{source_id}/report")
def report_scandal_source(
    scandal_id: int, 
    source_id: int, 
    db: Session = Depends(get_db)
):
    """Flag a source as reported (public endpoint)."""
    source = db.query(ScandalSource).filter(
        ScandalSource.id == source_id,
        ScandalSource.scandal_id == scandal_id
    ).first()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    source.is_reported = True
    db.commit()
    return {"message": "Source reported successfully", "is_reported": True}
