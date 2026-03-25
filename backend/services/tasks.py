"""
Background tasks — auto-scan Top 50 Global playlists.

Fetches artists from Spotify's Top 50 Global and Viral 50 Global playlists,
upserts them into the database (auto-approved), and triggers the scanner.
"""

import os
import sys
import json
import tempfile
import subprocess
from datetime import datetime, timezone, timedelta

from database import SessionLocal
from models import Artist, Scandal
from services.spotify import fetch_playlist

# Spotify curated playlist IDs
TOP50_GLOBAL = "37i9dQZEVXbMDoHDwVN2tF"
VIRAL50_GLOBAL = "37i9dQZEVXbLiRSasKsNU9"


async def run_top50_auto_scan():
    """
    Full pipeline: fetch Top 50 + Viral 50 playlists, upsert artists,
    auto-approve, and trigger the scanner for those needing a scan.
    """
    print("[AutoScan] Starting Top 50 auto-scan...")

    # 1. Fetch artists from both playlists
    all_artists: dict[str, dict] = {}  # spotify_id → artist data

    for playlist_id in [TOP50_GLOBAL, VIRAL50_GLOBAL]:
        try:
            result = await fetch_playlist(playlist_id)
            for a in result["artists"]:
                if a["spotify_id"] not in all_artists:
                    all_artists[a["spotify_id"]] = a
            print(f"[AutoScan] Fetched {len(result['artists'])} artists from {result['playlist_name']}")
        except Exception as e:
            print(f"[AutoScan] Failed to fetch playlist {playlist_id}: {e}")

    if not all_artists:
        print("[AutoScan] No artists fetched. Aborting.")
        return

    print(f"[AutoScan] Total unique artists: {len(all_artists)}")

    # 2. Upsert into DB (auto-approve)
    db = SessionLocal()
    try:
        added = 0
        for artist_data in all_artists.values():
            existing = db.query(Artist).filter(
                Artist.spotify_id == artist_data["spotify_id"]
            ).first()
            if existing:
                # Ensure auto-approved
                if not existing.approved:
                    existing.approved = True
                continue

            artist = Artist(
                name=artist_data["name"],
                spotify_id=artist_data["spotify_id"],
                image_url=artist_data.get("image_url"),
                approved=True,  # Auto-approve Top 50 artists
            )
            db.add(artist)
            added += 1

        db.commit()
        print(f"[AutoScan] Added {added} new artists, {len(all_artists) - added} already existed.")

        # 3. Collect artists that need scanning (not scanned in the last 4 weeks)
        four_weeks_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(weeks=4)
        spotify_ids = list(all_artists.keys())

        db_artists = db.query(Artist).filter(Artist.spotify_id.in_(spotify_ids)).all()
        artists_to_scan = []
        for a in db_artists:
            last_scan = a.last_scanned_at
            if last_scan:
                last_scan = last_scan.replace(tzinfo=None)
            if last_scan is None or last_scan < four_weeks_ago:
                existing_scandals = [
                    {"title": s.title, "description": s.description}
                    for s in db.query(Scandal).filter(Scandal.artist_id == a.id).all()
                ]
                artists_to_scan.append({
                    "id": a.id,
                    "name": a.name,
                    "spotify_id": a.spotify_id,
                    "existing_scandals": existing_scandals,
                })

        if not artists_to_scan:
            print("[AutoScan] All Top 50 artists have been scanned recently. Nothing to do.")
            return

        print(f"[AutoScan] Triggering scan for {len(artists_to_scan)} artists.")

    finally:
        db.close()

    # 4. Trigger detached scanner process (reuse existing pattern from scandals router)
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lock_path = os.path.join(backend_dir, "scan.lock")
    if os.path.exists(lock_path):
        print("[AutoScan] A scan is already in progress. Skipping.")
        return

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(artists_to_scan, tmp)
        tmp_path = tmp.name

    cli_path = os.path.join(backend_dir, "scanner_cli.py")
    python_exe = sys.executable

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    try:
        subprocess.Popen(
            [python_exe, cli_path, tmp_path],
            cwd=backend_dir,
            creationflags=creationflags,
            start_new_session=True if sys.platform != "win32" else False,
        )
        print("[AutoScan] Scanner process launched successfully.")
    except Exception as e:
        print(f"[AutoScan] Failed to launch scanner: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
