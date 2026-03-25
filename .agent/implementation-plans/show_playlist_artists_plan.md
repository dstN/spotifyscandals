# Implementation Plan: Show Playlist Artists after Submission

## Goal
Right after a user (including logged out public users) submits a playlist, the UI should immediately display a grid of the artists from that playlist instead of just numbers (added/skipped). It should only display the artists if they exist in the DB and preferably if they have scandals.

## Problem Context
Currently, `POST /api/playlists/submit` only returns an integer count of how many artists were added or skipped. The frontend doesn't actually know *which* artists were in the playlist.

## Proposed Changes

---

### 1. Backend: API Response
#### [MODIFY] backend/schemas.py
  - Add a field `artists: list[ArtistResponse]` or `list[ArtistBase]` to `PlaylistSubmitResponse`.

#### [MODIFY] backend/routers/playlists.py
  - During the playlist extraction loop, build a list of all artists found.
  - Fetch those artists from the DB (to get their actual IDs and `scandal_count`).
  - Return this list in the response.

---

### 2. Frontend: UI Integration
#### [MODIFY] frontend/src/routes/Submit.svelte
  - Wait for the API response which now contains `result.artists`.
  - Pass this array of artists to the UI.
  - Under the "Extraction Complete" success block, render a grid identical to the one on `Home.svelte` (e.g., using a shared `<ArtistGrid />` component, or just inline code), filtered to show artists inside the returned array.
  - *Alternative:* Automatically redirect to `/#/search?playlist_id=123` if we store playlists as entities, but we don't. So rendering them directly on the `Submit.svelte` success screen is the cleanest approach.

---

## Verification Plan
1. Submit a playlist URL natively on the frontend without being logged in.
2. Confirm the success screen accurately renders cards for the specific artists from that playlist.
