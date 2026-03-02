import sys
import json
import asyncio
import os
from datetime import datetime, timezone

# Add the current directory to sys.path to allow importing local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import Artist, Scandal, ScandalSource
from services.gemini import scan_artists_for_scandals, _resolve_url_deep, verify_source_relevance, find_better_sources
import logging

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
    Loop through newly found scandals, verify their sources, delete irrelevant ones,
    and attempt to 'heal' scandals that run out of sources.
    """
    if not new_scandal_ids:
        return

    print(f"\n[Scanner-CLI] Starting Source Verification for {len(new_scandal_ids)} new scandal(s)...")
    
    scandals = db.query(Scandal).filter(Scandal.id.in_(new_scandal_ids)).all()
    
    for scandal in scandals:
        artist_name = artist_name_map.get(scandal.artist_id, "Unknown Artist")
        print(f"\n[Scanner-CLI] --- Verifying Scandal: {scandal.title} ({artist_name}) ---")
        
        sources = db.query(ScandalSource).filter(ScandalSource.scandal_id == scandal.id).all()
        valid_sources_count = len(sources)
        
        # 1. Verify existing sources
        verified_count = 0
        for src in sources:
            is_valid = await verify_source_relevance(src.source_url, scandal.title, scandal.description)
            src.is_verified = is_valid
            if not is_valid:
                print(f"[Scanner-CLI] ❌ Source irrelevant (Unverified): {src.source_url[:60]}...")
            else:
                print(f"[Scanner-CLI] ✅ Source verified: {src.source_url[:60]}...")
                verified_count += 1
                
        db.commit()
        
        # 2. Healing Loop: If 0 verified sources, try to find new ones
        if verified_count == 0:
            print(f"[Scanner-CLI] ⚠️ Scandal lost all sources. Initiating healing loop...")
            new_sources_data = await find_better_sources(artist_name, scandal.title, scandal.description)
            
            healed = False
            for src_data in new_sources_data:
                url = src_data.get("url")
                title = src_data.get("title")
                if not url:
                     continue
                     
                print(f"[Scanner-CLI] Checking new candidate source: {url[:60]}...")
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
                    print(f"[Scanner-CLI] ➖ Healing found irrelevant source. Adding as unverified.")
                    new_src = ScandalSource(
                        scandal_id=scandal.id,
                        source_url=url,
                        source_title=title,
                        is_verified=False
                    )
                    db.add(new_src)
            
            db.commit()
            
            # 3. Final verdict
            if not healed:
                print(f"[Scanner-CLI] ⚠️ Healing failed. Scandal '{scandal.title}' remains unverified.")
            else:
                print(f"[Scanner-CLI] 🏥 Scandal recovered with {verified_count} verified sources.")
        else:
             print(f"[Scanner-CLI] Verified. {verified_count} source(s) verified.")

        # Update the scandal verification status
        scandal.verified = (verified_count > 0)
        db.commit()

    print(f"\n[Scanner-CLI] Source Verification Complete.")

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

    print(f"[Scanner-CLI] Starting scan for {len(artist_data)} artists...")

    try:
        results = await scan_artists_for_scandals(artist_data)
        
        db = SessionLocal()
        newly_created_scandal_ids = []
        artist_name_map = {a["id"]: a["name"] for a in artist_data}
        
        try:
            for artist_result in results:
                artist_id = artist_result.get("artist_id")
                
                # Update last scanned time
                db_artist = db.query(Artist).filter(Artist.id == artist_id).first()
                if db_artist:
                    db_artist.last_scanned_at = datetime.now(timezone.utc)

                for scandal_data in artist_result.get("scandals", []):
                    if not isinstance(scandal_data, dict):
                        continue
                        
                    raw_description = scandal_data.get("description")
                    description = str(raw_description).strip() if raw_description is not None else ""
                    
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

                    raw_title = scandal_data.get("title")
                    title = str(raw_title).strip() if raw_title is not None else ""

                    scandal = Scandal(
                        artist_id=artist_id,
                        title=title,
                        description=description,
                        verified=False,
                    )
                    db.add(scandal)
                    db.flush() # Flush to get scandal.id
                    newly_created_scandal_ids.append(scandal.id)

                    for source_item in scandal_data.get("sources", []):
                        if source_item is None:
                            continue
                            
                        if isinstance(source_item, dict):
                            raw_url = source_item.get("url")
                            url = str(raw_url).strip() if raw_url is not None else ""
                            src_title = source_item.get("title")
                        else:
                            url = str(source_item).strip()
                            src_title = None

                        if url:
                            source = ScandalSource(
                                scandal_id=scandal.id,
                                source_url=url,
                                source_title=src_title,
                            )
                            db.add(source)

            db.commit()
            print(f"[Scanner-CLI] Initial scan DB insertions completed.")
            
            # ─── Post-Scan Cleanup ───
            await cleanup_redirects(db)
            
            # ─── Post-Scan Verification & Healing ───
            await verify_and_heal_scandals(db, newly_created_scandal_ids, artist_name_map)
            
            print(f"[Scanner-CLI] Full scan cycle finished successfully. Updated {len(results)} artists.")
            
        except Exception as e:
            db.rollback()
            print(f"[Scanner-CLI] Database update failed: {e}")
            raise
        finally:
            db.close()
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
