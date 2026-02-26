from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import CommunityScandal, Scandal, ScandalSource, Artist
from schemas import CommunityScandalResponse, ScandalResponse
from auth_deps import require_admin
from datetime import datetime, timezone

router = APIRouter(prefix="/api/community-scandals", tags=["Community Scandals"])

@router.get("", response_model=list[CommunityScandalResponse])
def get_pending_submissions(db: Session = Depends(get_db), admin: str = Depends(require_admin)):
    """Fetch all pending community submissions globally."""
    submissions = db.query(CommunityScandal)\
        .options(joinedload(CommunityScandal.artist))\
        .order_by(CommunityScandal.created_at.desc())\
        .all()
    return submissions

@router.get("/artist/{artist_id}", response_model=list[CommunityScandalResponse])
def get_artist_submissions(artist_id: int, db: Session = Depends(get_db), admin: str = Depends(require_admin)):
    """Fetch pending community submissions for a specific artist."""
    submissions = db.query(CommunityScandal)\
        .options(joinedload(CommunityScandal.artist))\
        .filter(CommunityScandal.artist_id == artist_id)\
        .order_by(CommunityScandal.created_at.desc())\
        .all()
    return submissions

@router.post("/{submission_id}/verify", response_model=ScandalResponse)
def verify_community_submission(
    submission_id: int,
    title: str = Body(...),
    description: str = Body(...),
    source_urls: list[str] = Body([]),
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin)
):
    """
    Accepts an admin's final edits for a community submission.
    Creates a verified Scandal and associated sources, then deletes the pending submission.
    """
    submission = db.query(CommunityScandal).filter(CommunityScandal.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Community submission not found")

    artist = db.query(Artist).filter(Artist.id == submission.artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Associated artist not found")

    # 1. Create the permanent Scandal
    new_scandal = Scandal(
        artist_id=submission.artist_id,
        title=title.strip() if title else "Community Scandal",
        description=description.strip(),
        date_detected=datetime.now(timezone.utc),
        verified=True,          # Verified instantly since admin approved it
        is_community=True       # Flag it for the frontend UI
    )
    db.add(new_scandal)
    db.flush() # get new_scandal.id

    # 2. Add Sources
    for url in source_urls:
        if url.strip():
            src = ScandalSource(scandal_id=new_scandal.id, source_url=url.strip())
            db.add(src)

    # 3. Delete the pending submission
    db.delete(submission)
    db.commit()

    # 4. Fetch the fully loaded saved entity to return
    saved_scandal = db.query(Scandal).options(joinedload(Scandal.sources)).filter(Scandal.id == new_scandal.id).first()
    
    return ScandalResponse(
        id=saved_scandal.id,
        artist_id=saved_scandal.artist_id,
        artist_name=artist.name,
        title=saved_scandal.title,
        description=saved_scandal.description,
        date_detected=saved_scandal.date_detected,
        verified=saved_scandal.verified,
        is_community=saved_scandal.is_community,
        average_vote=None,
        vote_count=0,
        user_vote=None,
        sources=[{"id": src.id, "source_url": src.source_url, "created_at": src.created_at} for src in saved_scandal.sources]
    )


@router.delete("/{submission_id}")
def delete_community_submission(submission_id: int, db: Session = Depends(get_db), admin: str = Depends(require_admin)):
    """Reject and delete a community submission entirely."""
    submission = db.query(CommunityScandal).filter(CommunityScandal.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Community submission not found")
        
    db.delete(submission)
    db.commit()
    return {"detail": "Submission rejected and deleted."}
