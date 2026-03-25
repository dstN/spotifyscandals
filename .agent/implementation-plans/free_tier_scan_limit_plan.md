# Implementation Plan: Scanner Rate Limiting (Free vs Unlimited Tier)

## Goal
To prevent accidental API costs (specifically for the Google Gemini Search Grounding API, which allows ~1,500 free requests per day), the scanner needs a configurable execution limit.
We will add a toggle/setting in the Admin UI and the backend scanner logic to run in either "Free Tier" mode (stops when approaching the daily search grounding limit) or "Unlimited" mode (uses the configured credit balance).

## Proposed Changes

---

### 1. Database: System Settings
#### [MODIFY] backend/models.py
- Add a generic `SystemSettings` table (key-value pair) or specific columns if we already have one.
- Specifically we need a `scanner_mode` configuration, which can be `FREE_TIER` or `UNLIMITED`.
- Alternatively, include this setting as an environment or `.env` variable if database UI isn't preferred. For an Admin feature, a DB table is cleaner.

---

### 2. Backend: API Rate Limiter Logic
#### [MODIFY] backend/services/gemini.py
- Track daily usage of the `google_search` grounding tool internally or via SQLite.
- Before executing `_resolve_url_ultra` or `find_better_sources`, check remaining quota if in `FREE_TIER` mode.
- If daily API usage hits `~1450`, safely pause/abort the remaining artist scans for the day and log a "Rate Limit Reached - Paused until tomorrow" message.

#### [MODIFY] backend/routers/scandals.py
- Update the `/scan` endpoint to check the `scanner_mode` setting.
- In `FREE_TIER` mode, only load as many artists as the daily quota permits (roughly 1,450 grounding calls divided by an average of 4-5 source calls = ~250 artists/day).

---

### 3. Frontend: Admin Settings Toggle
#### [NEW] frontend/src/routes/admin/Settings.svelte (Or append to existing dashboard)
- Add a new "Scanner Limits" UI block.
- Toggle between:
  - **Free Tier (Safe Mode)**: Caps Google Search Grounding API requests at 1,450/day.
  - **Unlimited (Paid Mode)**: Scans all pending artists without a daily cap.
- Display the current estimated daily usage.

---

## Verification Plan
1. Admin switches to "Free Tier" mode.
2. We trigger a scan for 500 artists.
3. Observe that the backend halts processing gracefully and logs out near 1,450 search tool invocations to stay inside the 1.5K free limits without throwing hard HTTP 429 exceptions.
4. Admin switches to "Unlimited", triggering the remaining artists successfully.
