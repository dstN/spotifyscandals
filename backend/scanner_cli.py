import sys
import json
import asyncio
import os
from datetime import datetime, timezone

# Add the current directory to sys.path to allow importing local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import Artist, Scandal, ScandalSource, BatchJob
from services.gemini import scan_artists_for_scandals, _resolve_url_deep, verify_source_relevance, find_better_sources, score_source_relevance, is_blocked_domain, get_rate_limiter, submit_batch_job
import logging

# Global lock — ensures only one artist writes to SQLite at a time.
# Scanning, scoring, and content-fetching still happens fully in parallel.
_db_write_lock = asyncio.Lock()

class LoggerWriter:
    def __init__(self, log_file_path, original_stream):
        self.log_file = open(log_file_path, "a", encoding="utf-8")
        self.original_stream = original_stream

    def write(self, message):
        self.original_stream.write(message)
        self.log_file.write(message)
        self.flush()

    def flush(self):
        self.original_stream.flush()
        self.log_file.flush()

async def cleanup_redirects(db):
    """Loop through DB and resolve any remaining vertexaisearch URLs."""
    redirect_prefix = "https://vertexaisearch.cloud.google.com/"
    sources = db.query(ScandalSource).filter(ScandalSource.source_url.like(f"{redirect_prefix}%")).all()
    
    if not sources:
        return

    print(f"[Scanner-CLI] Found {len(sources)} unresolved redirect(s). Cleaning up...")
    
    for src in sources:
        try:
            print(f"[Scanner-CLI] Resolving: {src.source_url[:60]}...")
            resolved = await _resolve_url_deep(src.source_url, src.source_title)
            if resolved["url"] != src.source_url:
                src.source_url = resolved["url"]
                if resolved["title"]:
                    src.source_title = resolved["title"]
                print(f"[Scanner-CLI] Fixed -> {src.source_url[:60]}")
        except Exception as e:
            print(f"[Scanner-CLI] Cleanup failed for {src.id}: {e}")
    
    db.commit()

async def verify_and_heal_scandals(db, new_scandal_ids: list[int], artist_name_map: dict):
    """
    Loop through newly found scandals, pre-score and verify their sources,
    and attempt to 'heal' scandals that run out of verified sources.
    """
    if not new_scandal_ids:
        return

    MAX_SOURCES = 5
    MIN_SCORE = 8  # Pre-filter threshold (0-10 scale)

    print(f"\n[Scanner-CLI] Starting Source Verification for {len(new_scandal_ids)} new scandal(s)...")
    
    scandals = db.query(Scandal).filter(Scandal.id.in_(new_scandal_ids)).all()
    
    for scandal in scandals:
        artist_name = artist_name_map.get(scandal.artist_id, "Unknown Artist")
        print(f"\n[Scanner-CLI] --- Verifying Scandal: {scandal.title} ({artist_name}) ---")
        
        sources = db.query(ScandalSource).filter(ScandalSource.scandal_id == scandal.id).all()
        
        # 1. Pre-score + Verify existing sources (cap at MAX_SOURCES verified)
        verified_count = 0
        for src in sources:
            # Blocked domain fast-reject
            if is_blocked_domain(src.source_url):
                print(f"[Scanner-CLI] 🚫 Blocked domain, skipping: {src.source_url[:60]}")
                src.is_verified = False
                continue

            # Pre-score to avoid expensive content fetch
            if verified_count < MAX_SOURCES:
                score = await score_source_relevance(src.source_url, scandal.title, scandal.description)
                if score < MIN_SCORE:
                    print(f"[Scanner-CLI] ⬇️ Score {score}/10 too low, skipping deep verify: {src.source_url[:60]}")
                    src.is_verified = False
                    continue

                is_valid = await verify_source_relevance(src.source_url, scandal.title, scandal.description)
                src.is_verified = is_valid
                if is_valid:
                    print(f"[Scanner-CLI] ✅ Source verified: {src.source_url[:60]}")
                    verified_count += 1
                else:
                    print(f"[Scanner-CLI] ❌ Source irrelevant: {src.source_url[:60]}")
            else:
                # Already have enough verified sources — mark the rest unverified
                src.is_verified = False
                print(f"[Scanner-CLI] 🔢 Source cap reached ({MAX_SOURCES}), skipping: {src.source_url[:60]}")
                
        db.commit()
        
        # 2. Healing Loop: If 0 verified sources, try to find new ones
        if verified_count == 0:
            print(f"[Scanner-CLI] ⚠️ Scandal lost all sources. Initiating healing loop...")
            new_sources_data = await find_better_sources(artist_name, scandal.title, scandal.description)
            
            healed = False
            for src_data in new_sources_data:
                if verified_count >= MAX_SOURCES:
                    break

                url = src_data.get("url")
                title = src_data.get("title")
                if not url or is_blocked_domain(url):
                    continue
                    
                print(f"[Scanner-CLI] Checking heal candidate: {url[:60]}...")
                
                # Pre-score the heal candidate too
                score = await score_source_relevance(url, scandal.title, scandal.description)
                if score < MIN_SCORE:
                    print(f"[Scanner-CLI] ⬇️ Heal candidate score too low ({score}/10), skipping.")
                    continue
                
                is_valid = await verify_source_relevance(url, scandal.title, scandal.description)
                
                if is_valid:
                    print(f"[Scanner-CLI] 💉 Healing successful! Adding verified source.")
                    new_src = ScandalSource(
                        scandal_id=scandal.id,
                        source_url=url,
                        source_title=title,
                        is_verified=True
                    )
                    db.add(new_src)
                    healed = True
                    verified_count += 1
                else:
                    print(f"[Scanner-CLI] ➖ Heal candidate failed deep verify. Skipping.")
            
            db.commit()
            
            # 3. Final verdict
            if not healed:
                print(f"[Scanner-CLI] ⚠️ Healing failed. Scandal '{scandal.title}' remains unverified.")
            else:
                print(f"[Scanner-CLI] 🏥 Scandal recovered with {verified_count} verified sources.")
        else:
             print(f"[Scanner-CLI] ✓ Verified. {verified_count}/{MAX_SOURCES} max source(s).")

        # Update the scandal verification status
        scandal.verified = (verified_count > 0)
        db.commit()

    print(f"\n[Scanner-CLI] Source Verification Complete.")

async def process_artist(artist: dict, artist_name_map: dict, semaphore: asyncio.Semaphore) -> int:
    """Process a single artist: scan for scandals, verify sources inline, then save to DB."""
    MAX_SOURCES = 5
    MIN_SCORE = 7  # Sources must score > 7 (i.e. 8, 9, or 10) to be accepted

    async with semaphore:
        print(f"\n[Scanner-CLI] === Processing Artist: {artist['name']} ===")
        try:
            # 0. Fetch existing scandal titles so Gemini won't re-generate them
            try:
                with SessionLocal() as db:
                    existing_rows = (
                        db.query(Scandal.title, Scandal.description)
                        .filter(Scandal.artist_id == artist["id"])
                        .all()
                    )
                    artist["existing_scandals"] = [
                        {"title": r.title, "description": r.description}
                        for r in existing_rows
                    ]
                    if artist["existing_scandals"]:
                        print(f"[Scanner-CLI] ℹ️ {len(artist['existing_scandals'])} existing scandal(s) will be excluded from scan.")
            except Exception as e:
                print(f"[Scanner-CLI] Could not fetch existing scandals: {e}")
                artist["existing_scandals"] = []

            # 1. Scan this single artist via Gemini
            results = await scan_artists_for_scandals([artist])
            if not results:
                return 0
            
            artist_result = results[0]
            artist_id = artist_result.get("artist_id")

            # ─── Phase 1: All expensive work (no DB open) ───
            # Score sources, run healing — DB is NOT open during this.
            # This can run fully in parallel across multiple artists.
            scandals_to_save = []

            for scandal_data in artist_result.get("scandals", []):
                if not isinstance(scandal_data, dict):
                    continue

                raw_description = scandal_data.get("description")
                description = str(raw_description).strip() if raw_description is not None else ""
                if not description:
                    continue

                raw_title = scandal_data.get("title")
                title = str(raw_title).strip() if raw_title is not None else ""

                accepted_sources = []
                raw_sources = scandal_data.get("sources", [])

                for source_item in raw_sources:
                    if len(accepted_sources) >= MAX_SOURCES:
                        break
                    if source_item is None:
                        continue

                    if isinstance(source_item, dict):
                        raw_url = source_item.get("url")
                        url = str(raw_url).strip() if raw_url is not None else ""
                        src_title = source_item.get("title")
                    else:
                        url = str(source_item).strip()
                        src_title = None

                    if not url or is_blocked_domain(url):
                        continue

                    score = await score_source_relevance(url, title, description)
                    if score <= MIN_SCORE:
                        print(f"[Scanner-CLI] ⬇️ Score {score}/10 too low (need >{MIN_SCORE}), skipping: {url[:60]}")
                        continue

                    print(f"[Scanner-CLI] ✅ Source accepted (score {score}/10): {url[:60]}")
                    accepted_sources.append({"url": url, "title": src_title})

                # Healing loop if nothing passed
                if not accepted_sources:
                    print(f"[Scanner-CLI] ⚠️ No sources passed gates for '{title}'. Starting healing loop...")
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
                            print(f"[Scanner-CLI] ⬇️ Heal candidate score too low ({score}/10), skipping.")
                            continue

                        print(f"[Scanner-CLI] 💉 Healing: accepted source (score {score}/10): {url[:60]}")
                        accepted_sources.append({"url": url, "title": src_title})

                    if not accepted_sources:
                        print(f"[Scanner-CLI] ⚠️ Healing failed. Scandal '{title}' has no verified sources.")

                scandals_to_save.append({
                    "title": title,
                    "description": description,
                    "verified": len(accepted_sources) > 0,
                    "sources": accepted_sources,
                })

            # ─── Phase 2: Write to DB (serialized via lock) ───
            # DB is open for milliseconds — just writes, no I/O or API calls.
            async with _db_write_lock:
                db = SessionLocal()
                try:
                    db_artist = db.query(Artist).filter(Artist.id == artist_id).first()
                    if db_artist:
                        db_artist.last_scanned_at = datetime.now(timezone.utc)

                    for s in scandals_to_save:
                        existing = (
                            db.query(Scandal)
                            .filter(Scandal.artist_id == artist_id, Scandal.description == s["description"])
                            .first()
                        )
                        if existing:
                            continue

                        scandal = Scandal(
                            artist_id=artist_id,
                            title=s["title"],
                            description=s["description"],
                            verified=s["verified"],
                        )
                        db.add(scandal)
                        db.flush()

                        for src in s["sources"]:
                            db.add(ScandalSource(
                                scandal_id=scandal.id,
                                source_url=src["url"],
                                source_title=src["title"],
                                is_verified=True,
                            ))
                        print(f"[Scanner-CLI] Scandal '{s['title']}': {len(s['sources'])} verified source(s) written.")

                    db.commit()
                    print(f"[Scanner-CLI] ✓ All data saved for {artist['name']}.")
                    return 1

                except Exception as e:
                    db.rollback()
                    print(f"[Scanner-CLI] Database update failed for {artist['name']}: {e}")
                    return 0
                finally:
                    db.close()
                
        except RuntimeError as e:
            # Rate limit exhausted — propagate to stop remaining tasks
            print(f"[Scanner-CLI] ⛔ Rate limit hit for {artist['name']}: {e}")
            raise
        except Exception as e:
            print(f"[Scanner-CLI] Gemini scan crashed for {artist['name']}: {e}")
            return 0


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scanner_cli.py <path_to_json>")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base_dir, "..", "scan.log")
    # Duplicate stdout/stderr to both the original terminal and the log file
    sys.stdout = LoggerWriter(log_path, sys.stdout)
    sys.stderr = sys.stdout

    try:
        json_path = sys.argv[1]
    except IndexError:
        print("Usage: python scanner_cli.py <path_to_json>")
        sys.exit(1)

    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        sys.exit(1)

    try:
        with open(json_path, 'r') as f:
            artist_data = json.load(f)
    except Exception as e:
        print(f"Failed to read JSON: {e}")
        sys.exit(1)

    # ─── Batch Mode (default — 50% token cost discount) ───
    # Use --sync to force synchronous real-time scanning instead.
    if "--sync" not in sys.argv:
        print(f"[Scanner-CLI] Batch mode (default): submitting {len(artist_data)} artists to Gemini Batch API...")

        # Enrich artists with existing scandals to avoid duplicates
        with SessionLocal() as db:
            for artist in artist_data:
                existing_rows = (
                    db.query(Scandal.title, Scandal.description)
                    .filter(Scandal.artist_id == artist["id"])
                    .all()
                )
                artist["existing_scandals"] = [
                    {"title": r.title, "description": r.description}
                    for r in existing_rows
                ]

        try:
            job_name = submit_batch_job(artist_data)
        except Exception as e:
            print(f"[Scanner-CLI] Batch submission failed: {e}")
            sys.exit(1)

        # Save BatchJob to DB
        with SessionLocal() as db:
            batch_job = BatchJob(
                job_name=job_name,
                status="PENDING",
                artist_ids_json=json.dumps([a["id"] for a in artist_data]),
            )
            db.add(batch_job)
            db.commit()
            print(f"[Scanner-CLI] BatchJob saved (id={batch_job.id}, job_name={job_name})")

        print(f"[Scanner-CLI] Batch submitted. Use batch_poller.py to poll for results.")

        # Cleanup temp file
        try:
            if os.path.exists(json_path):
                os.remove(json_path)
        except Exception:
            pass
        return

    # ─── Synchronous Mode (opt-in via --sync) ───
    print(f"[Scanner-CLI] Sync mode (--sync): scanning {len(artist_data)} artists in real-time (max 5 parallel)...")

    limiter = get_rate_limiter()
    print(f"[Scanner-CLI] Rate limiter mode: {limiter.mode} | Model RPD: {limiter.model_rpd} | Search RPD: {limiter.search_rpd}")

    artist_name_map = {a["id"]: a["name"] for a in artist_data}
    
    # ─── Process concurrently with a Semaphore ───
    semaphore = asyncio.Semaphore(5)
    
    try:
        tasks = [
            process_artist(artist, artist_name_map, semaphore)
            for artist in artist_data
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes vs rate-limit stops
        total_processed = 0
        rate_limited = False
        for r in results:
            if isinstance(r, RuntimeError):
                rate_limited = True
            elif isinstance(r, int):
                total_processed += r

        stats = limiter.stats
        print(f"\n[Scanner-CLI] Full scan cycle finished. Processed {total_processed} artists.")
        print(f"[Scanner-CLI] Rate limiter stats: Model {stats['model_rpd_used']}/{stats['model_rpd_limit']} RPD | Search {stats['search_rpd_used']}/{stats['search_rpd_limit']} RPD")
        if rate_limited:
            print(f"[Scanner-CLI] ⛔ Some artists were skipped due to rate limits. Re-run tomorrow or switch to unlimited mode.")
            
    except Exception as e:
        print(f"[Scanner-CLI] CLI scan crash: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup temporary file
        try:
            if os.path.exists(json_path):
                os.remove(json_path)
                print(f"[Scanner-CLI] Cleaned up temp file: {json_path}")
        except Exception as e:
            print(f"[Scanner-CLI] Cleanup failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
