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

logger = logging.getLogger(__name__)

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

    def close(self):
        if self.log_file and not self.log_file.closed:
            self.log_file.close()

async def cleanup_redirects(db):
    """Loop through DB and resolve any remaining vertexaisearch URLs."""
    redirect_prefix = "https://vertexaisearch.cloud.google.com/"
    sources = db.query(ScandalSource).filter(ScandalSource.source_url.like(f"{redirect_prefix}%")).all()
    
    if not sources:
        return

    logger.info("Found %s unresolved redirect(s). Cleaning up...", len(sources))
    
    for src in sources:
        try:
            logger.info("Resolving: %s...", src.source_url[:60])
            resolved = await _resolve_url_deep(src.source_url, src.source_title)
            if resolved["url"] != src.source_url:
                src.source_url = resolved["url"]
                if resolved["title"]:
                    src.source_title = resolved["title"]
                logger.info("Fixed -> %s", src.source_url[:60])
        except Exception as e:
            logger.exception("Cleanup failed for %s: %s", src.id, e)
    
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

    logger.info("Starting Source Verification for %s new scandal(s)...", len(new_scandal_ids))
    
    scandals = db.query(Scandal).filter(Scandal.id.in_(new_scandal_ids)).all()
    
    for scandal in scandals:
        artist_name = artist_name_map.get(scandal.artist_id, "Unknown Artist")
        logger.info("--- Verifying Scandal: %s (%s) ---", scandal.title, artist_name)
        
        sources = db.query(ScandalSource).filter(ScandalSource.scandal_id == scandal.id).all()
        
        # 1. Pre-score + Verify existing sources (cap at MAX_SOURCES verified)
        verified_count = 0
        for src in sources:
            # Blocked domain fast-reject
            if is_blocked_domain(src.source_url):
                logger.warning("🚫 Blocked domain, skipping: %s", src.source_url[:60])
                src.is_verified = False
                continue

            # Pre-score to avoid expensive content fetch
            if verified_count < MAX_SOURCES:
                score = await score_source_relevance(src.source_url, scandal.title, scandal.description)
                if score < MIN_SCORE:
                    logger.warning("⬇️ Score %s/10 too low, skipping deep verify: %s", score, src.source_url[:60])
                    src.is_verified = False
                    continue

                is_valid = await verify_source_relevance(src.source_url, scandal.title, scandal.description)
                src.is_verified = is_valid
                if is_valid:
                    logger.info("✅ Source verified: %s", src.source_url[:60])
                    verified_count += 1
                else:
                    logger.info("❌ Source irrelevant: %s", src.source_url[:60])
            else:
                # Already have enough verified sources — mark the rest unverified
                src.is_verified = False
                logger.warning("🔢 Source cap reached (%s), skipping: %s", MAX_SOURCES, src.source_url[:60])
                
        db.commit()
        
        # 2. Healing Loop: If 0 verified sources, try to find new ones
        if verified_count == 0:
            logger.warning("⚠️ Scandal lost all sources. Initiating healing loop...")
            new_sources_data = await find_better_sources(artist_name, scandal.title, scandal.description)
            
            healed = False
            for src_data in new_sources_data:
                if verified_count >= MAX_SOURCES:
                    break

                url = src_data.get("url")
                title = src_data.get("title")
                if not url or is_blocked_domain(url):
                    continue
                    
                logger.info("Checking heal candidate: %s...", url[:60])
                
                # Pre-score the heal candidate too
                score = await score_source_relevance(url, scandal.title, scandal.description)
                if score < MIN_SCORE:
                    logger.warning("⬇️ Heal candidate score too low (%s/10), skipping.", score)
                    continue
                
                is_valid = await verify_source_relevance(url, scandal.title, scandal.description)
                
                if is_valid:
                    logger.info("💉 Healing successful! Adding verified source.")
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
                    logger.warning("➖ Heal candidate failed deep verify. Skipping.")
            
            db.commit()
            
            # 3. Final verdict
            if not healed:
                logger.warning("⚠️ Healing failed. Scandal '%s' remains unverified.", scandal.title)
            else:
                logger.info("🏥 Scandal recovered with %s verified sources.", verified_count)
        else:
             logger.info("✓ Verified. %s/%s max source(s).", verified_count, MAX_SOURCES)

        # Update the scandal verification status
        scandal.verified = (verified_count > 0)
        db.commit()

    logger.info("Source Verification Complete.")

async def process_artist(artist: dict, artist_name_map: dict, semaphore: asyncio.Semaphore) -> int:
    """Process a single artist: scan for scandals, verify sources inline, then save to DB."""
    MAX_SOURCES = 5
    MIN_SCORE = 7  # Sources must score > 7 (i.e. 8, 9, or 10) to be accepted

    async with semaphore:
        logger.info("=== Processing Artist: %s ===", artist['name'])
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
                        logger.info("ℹ️ %s existing scandal(s) will be excluded from scan.", len(artist['existing_scandals']))
            except Exception as e:
                logger.info("Could not fetch existing scandals: %s", e)
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
                        logger.warning("⬇️ Score %s/10 too low (need >%s), skipping: %s", score, MIN_SCORE, url[:60])
                        continue

                    logger.info("✅ Source accepted (score %s/10): %s", score, url[:60])
                    accepted_sources.append({"url": url, "title": src_title})

                # Healing loop if nothing passed
                if not accepted_sources:
                    logger.warning("⚠️ No sources passed gates for '%s'. Starting healing loop...", title)
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
                            logger.warning("⬇️ Heal candidate score too low (%s/10), skipping.", score)
                            continue

                        logger.info("💉 Healing: accepted source (score %s/10): %s", score, url[:60])
                        accepted_sources.append({"url": url, "title": src_title})

                    if not accepted_sources:
                        logger.warning("⚠️ Healing failed. Scandal '%s' has no verified sources.", title)

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
                        logger.info("Scandal '%s': %s verified source(s) written.", s['title'], len(s['sources']))

                    db.commit()
                    logger.info("✓ All data saved for %s.", artist['name'])
                    return 1

                except Exception as e:
                    db.rollback()
                    logger.exception("Database update failed for %s: %s", artist['name'], e)
                    return 0
                finally:
                    db.close()
                
        except RuntimeError as e:
            # Rate limit exhausted — propagate to stop remaining tasks
            logger.error("⛔ Rate limit hit for %s: %s", artist['name'], e)
            raise
        except Exception as e:
            logger.exception("Gemini scan crashed for %s: %s", artist['name'], e)
            return 0


async def main():
    if len(sys.argv) < 2:
        logger.info("Usage: python scanner_cli.py <path_to_json>")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base_dir, "..", "scan.log")
    # Duplicate stdout/stderr to both the original terminal and the log file
    sys.stdout = LoggerWriter(log_path, sys.stdout)
    sys.stderr = sys.stdout

    try:
        json_path = sys.argv[1]
    except IndexError:
        logger.info("Usage: python scanner_cli.py <path_to_json>")
        sys.exit(1)

    if not os.path.exists(json_path):
        logger.info("File not found: %s", json_path)
        sys.exit(1)

    try:
        with open(json_path, 'r') as f:
            artist_data = json.load(f)
    except Exception as e:
        logger.exception("Failed to read JSON: %s", e)
        sys.exit(1)

    # ─── Batch Mode (default — 50% token cost discount) ───
    # Use --sync to force synchronous real-time scanning instead.
    if "--sync" not in sys.argv:
        logger.info("Batch mode (default): submitting %s artists to Gemini Batch API...", len(artist_data))

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
            logger.exception("Batch submission failed: %s", e)
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
            logger.info("BatchJob saved (id=%s, job_name=%s)", batch_job.id, job_name)

        logger.info("Batch submitted. Use batch_poller.py to poll for results.")

        # Cleanup temp file
        try:
            if os.path.exists(json_path):
                os.remove(json_path)
        except Exception:
            pass
        return

    # ─── Synchronous Mode (opt-in via --sync) ───
    logger.info("Sync mode (--sync): scanning %s artists in real-time (max 5 parallel)...", len(artist_data))

    limiter = get_rate_limiter()
    logger.info("Rate limiter mode: %s | Model RPD: %s | Search RPD: %s", limiter.mode, limiter.model_rpd, limiter.search_rpd)

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
        logger.info("Full scan cycle finished. Processed %s artists.", total_processed)
        logger.info("Rate limiter stats: Model %s/%s RPD | Search %s/%s RPD", stats['model_rpd_used'], stats['model_rpd_limit'], stats['search_rpd_used'], stats['search_rpd_limit'])
        if rate_limited:
            logger.error("⛔ Some artists were skipped due to rate limits. Re-run tomorrow or switch to unlimited mode.")
            
    except Exception as e:
        logger.exception("CLI scan crash: %s", e)
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup temporary file
        try:
            if os.path.exists(json_path):
                os.remove(json_path)
                logger.info("Cleaned up temp file: %s", json_path)
        except Exception as e:
            logger.exception("Cleanup failed: %s", e)

        # Remove the scan lock file so future scans can proceed
        lock_path = os.path.join(base_dir, "scan.lock")
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
                logger.info("Removed scan.lock")
        except OSError:
            pass

        # Close LoggerWriter file handles
        if hasattr(sys.stdout, 'close'):
            sys.stdout.close()

if __name__ == "__main__":
    asyncio.run(main())
