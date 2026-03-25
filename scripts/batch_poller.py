"""
Batch Poller — polls Gemini Batch API for completed jobs and processes results.

Usage:
    python scripts/batch_poller.py              # Poll once
    python scripts/batch_poller.py --loop 300   # Poll every 300 seconds
"""

import sys
import os
import json
import time
import asyncio
from datetime import datetime, timezone

# Add backend to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database import SessionLocal
from models import Artist, Scandal, ScandalSource, BatchJob
from services.gemini import (
    poll_batch_job,
    parse_batch_response,
    score_source_relevance,
    find_better_sources,
    is_blocked_domain,
    get_rate_limiter,
)


MAX_SOURCES = 5
MIN_SCORE = 7


async def process_completed_job(db, batch_job: BatchJob, poll_result: dict):
    """Process a completed batch job: parse responses, score sources, write scandals to DB."""
    responses = poll_result.get("responses", [])
    artist_ids = json.loads(batch_job.artist_ids_json)

    if len(responses) != len(artist_ids):
        print(f"[BatchPoller] ⚠️ Response count mismatch: {len(responses)} responses for {len(artist_ids)} artists")

    # Load artist info from DB
    artists_by_id = {}
    for artist_id in artist_ids:
        artist = db.query(Artist).filter(Artist.id == artist_id).first()
        if artist:
            artists_by_id[artist_id] = {"id": artist.id, "name": artist.name, "spotify_id": artist.spotify_id}

    total_scandals = 0

    for i, response in enumerate(responses):
        if i >= len(artist_ids):
            break

        artist_id = artist_ids[i]
        artist = artists_by_id.get(artist_id)
        if not artist:
            print(f"[BatchPoller] ⚠️ Artist ID {artist_id} not found in DB, skipping.")
            continue

        print(f"\n[BatchPoller] Processing response for {artist['name']}...")

        parsed = parse_batch_response(response, artist)
        scandals = parsed.get("scandals", [])

        for scandal_data in scandals:
            if not isinstance(scandal_data, dict):
                continue

            title = str(scandal_data.get("title", "")).strip()
            description = str(scandal_data.get("description", "")).strip()
            if not description:
                continue

            # Skip duplicates
            existing = (
                db.query(Scandal)
                .filter(Scandal.artist_id == artist_id, Scandal.description == description)
                .first()
            )
            if existing:
                print(f"[BatchPoller] Duplicate scandal skipped: {title[:50]}")
                continue

            # Score sources
            accepted_sources = []
            raw_sources = scandal_data.get("sources", [])

            for source_item in raw_sources:
                if len(accepted_sources) >= MAX_SOURCES:
                    break
                if not isinstance(source_item, dict):
                    continue

                url = str(source_item.get("url", "")).strip()
                src_title = source_item.get("title")
                if not url or is_blocked_domain(url):
                    continue

                score = await score_source_relevance(url, title, description)
                if score <= MIN_SCORE:
                    print(f"[BatchPoller] ⬇️ Score {score}/10 too low, skipping: {url[:60]}")
                    continue

                print(f"[BatchPoller] ✅ Source accepted (score {score}/10): {url[:60]}")
                accepted_sources.append({"url": url, "title": src_title})

            # Healing if no sources passed
            if not accepted_sources:
                print(f"[BatchPoller] ⚠️ No sources for '{title[:50]}'. Healing...")
                heal_sources = await find_better_sources(artist["name"], title, description)
                for src_data in heal_sources:
                    if len(accepted_sources) >= MAX_SOURCES:
                        break
                    url = src_data.get("url", "")
                    src_title = src_data.get("title")
                    if not url or is_blocked_domain(url):
                        continue
                    score = await score_source_relevance(url, title, description)
                    if score <= MIN_SCORE:
                        continue
                    print(f"[BatchPoller] 💉 Healed source (score {score}/10): {url[:60]}")
                    accepted_sources.append({"url": url, "title": src_title})

            # Write scandal to DB
            scandal = Scandal(
                artist_id=artist_id,
                title=title,
                description=description,
                verified=len(accepted_sources) > 0,
            )
            db.add(scandal)
            db.flush()

            for src in accepted_sources:
                db.add(ScandalSource(
                    scandal_id=scandal.id,
                    source_url=src["url"],
                    source_title=src["title"],
                    is_verified=True,
                ))

            total_scandals += 1
            print(f"[BatchPoller] Scandal '{title[:50]}': {len(accepted_sources)} verified source(s)")

        # Update artist last_scanned_at
        db_artist = db.query(Artist).filter(Artist.id == artist_id).first()
        if db_artist:
            db_artist.last_scanned_at = datetime.now(timezone.utc)

    # Mark batch job as completed
    batch_job.status = "SUCCEEDED"
    batch_job.completed_at = datetime.now(timezone.utc)
    db.commit()

    print(f"\n[BatchPoller] ✓ Job {batch_job.job_name} complete. {total_scandals} new scandal(s) written.")


async def poll_once():
    """Poll all active batch jobs once."""
    db = SessionLocal()
    try:
        active_jobs = (
            db.query(BatchJob)
            .filter(BatchJob.status.in_(["PENDING", "RUNNING"]))
            .all()
        )

        if not active_jobs:
            print("[BatchPoller] No active batch jobs.")
            return

        print(f"[BatchPoller] Polling {len(active_jobs)} active job(s)...")

        for batch_job in active_jobs:
            print(f"\n[BatchPoller] Checking job: {batch_job.job_name} (current: {batch_job.status})")

            try:
                result = poll_batch_job(batch_job.job_name)
            except Exception as e:
                print(f"[BatchPoller] ❌ Poll failed for {batch_job.job_name}: {e}")
                continue

            state = result.get("state", "UNKNOWN")
            print(f"[BatchPoller] State: {state}")

            if state == "JOB_STATE_SUCCEEDED":
                await process_completed_job(db, batch_job, result)

            elif state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"):
                batch_job.status = state.replace("JOB_STATE_", "")
                batch_job.completed_at = datetime.now(timezone.utc)
                db.commit()
                print(f"[BatchPoller] ⚠️ Job {batch_job.job_name} ended with state: {state}")

            elif state in ("JOB_STATE_PENDING", "JOB_STATE_RUNNING"):
                new_status = state.replace("JOB_STATE_", "")
                if batch_job.status != new_status:
                    batch_job.status = new_status
                    db.commit()
                print(f"[BatchPoller] ⏳ Job still {new_status.lower()}...")

            else:
                print(f"[BatchPoller] Unknown state: {state}")

    finally:
        db.close()


async def main():
    limiter = get_rate_limiter()
    print(f"[BatchPoller] Rate limiter mode: {limiter.mode} | Model RPD: {limiter.model_rpd} | Search RPD: {limiter.search_rpd}")

    loop_interval = None
    if "--loop" in sys.argv:
        idx = sys.argv.index("--loop")
        if idx + 1 < len(sys.argv):
            loop_interval = int(sys.argv[idx + 1])

    if loop_interval:
        print(f"[BatchPoller] Polling every {loop_interval} seconds. Press Ctrl+C to stop.")
        while True:
            await poll_once()
            print(f"[BatchPoller] Sleeping {loop_interval}s...")
            time.sleep(loop_interval)
    else:
        await poll_once()

    stats = limiter.stats
    print(f"[BatchPoller] Rate limiter stats: Model {stats['model_rpd_used']}/{stats['model_rpd_limit']} RPD | Search {stats['search_rpd_used']}/{stats['search_rpd_limit']} RPD")


if __name__ == "__main__":
    asyncio.run(main())
