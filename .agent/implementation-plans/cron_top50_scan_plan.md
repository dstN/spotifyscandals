# Implementation Plan: Auto-Scan Top 50 Global Artists

## Goal
Automatically fetch the Top 50 most popular artists globally every 4 weeks and scan them for new scandals. This ensures the tracker's database is always up-to-date with the artists people care about most right now.

**Target Playlists:**
1. Viral Top 50 Global (`37i9dQZEVXbLiRSasKsNU9`)
2. Top 50 Global (`37i9dQZEVXbMDoHDwVN2tF`)

## Architecture
We will write a dedicated standalone background script that performs the full pipeline (Playlist Extraction → DB Upsert → Auto Approve → AI Scan) without requiring manual admin intervention. For scheduling, we can either tie it into the FastAPI lifecycle using a lightweight scheduler like `APScheduler`, or provide a clean script intended for a standard server `cron` job. Given the simplicity, `APScheduler` inside FastAPI is preferred so it runs automatically as long as the backend is running.

## Proposed Changes

---

### 1. Requirements & Dependencies
#### [MODIFY] backend/requirements.txt
- Add `apscheduler==3.10.4` to handle the "every 4 weeks" interval natively within the Python event loop.

---

### 2. Auto-Scan Logic
#### [NEW] backend/services/tasks.py
- Create a new file for background tasks.
- Implement `async def run_top50_auto_scan()`:
  1. Call `spotify.extract_artists_from_playlist("37i9dQZEVXbLiRSasKsNU9")`
  2. Call `spotify.extract_artists_from_playlist("37i9dQZEVXbMDoHDwVN2tF")`
  3. Merge and deduplicate the artists.
  4. Upsert them into the database (`models.Artist`).
  5. Crucially: Automatically set `approved = True` for these specific artists so they bypass the manual admin approval queue.
  6. Trigger the `scanner_cli.py` or the `scan_artist_for_scandals` pipeline for these specific artists.
  
*(Note: To avoid hitting Gemini rate limits all at once, the scan pipeline should use the existing semaphore and process them cleanly).*

---

### 3. Scheduler Integration
#### [MODIFY] backend/main.py
- Import `AsyncIOScheduler` from `apscheduler.schedulers.asyncio`.
- In the FastAPI `@app.on_event("startup")` lifecycle hook:
  - Initialize the scheduler.
  - Add the `run_top50_auto_scan` job with a trigger of `interval`, `weeks=4` (or standard `cron` expression).
  - Start the scheduler.
- In the `@app.on_event("shutdown")` hook, gracefully shut down the scheduler.

---

### Alternate Approach (Cronjob Script)
If running a background task inside FastAPI isn't ideal for the server environment (e.g., if Phusion Passenger forks multiple workers leading to duplicate executions), we will instead:
1. Create `scripts/cron_top50_scan.py` with the logic from `tasks.py`.
2. Add instructions to the user to run `crontab -e` and add:
   `0 0 1 * * cd /path/to/backend && ./venv/bin/python ../scripts/cron_top50_scan.py`

*(We will ask the user which approach they prefer during implementation).*

## Verification Plan
1. Create a dummy endpoint `/api/admin/trigger-auto-scan` to manually fire the job and monitor text logs.
2. Verify that the 100+ artists from both playlists are successfully fetched, added to the database, auto-approved, and passed into the scanner.
3. Check the database to confirm no duplicate artists were created and scandals were attached.
