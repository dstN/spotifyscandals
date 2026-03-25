# Implementation Plan: User's Top Artists on Home Page

## Goal
When a user logs in via Spotify, display a personalized "Your Top Artists" section on the `Home.svelte` page. This section will show the user's most listened-to artists (that also exist and are approved in our database).

## Architecture & Data Flow
Currently, the backend performs the Spotify OAuth flow, generates its own internal JWT, and discards the Spotify access token. To fetch top artists on the client side without heavily modifying the backend to proxy Spotify requests, we will pass the short-lived Spotify `access_token` to the frontend alongside the internal JWT. The frontend will then call the Spotify API directly and intersect the results with the already loaded database artists.

## Proposed Changes

---

### 1. Backend: OAuth Token & Scope
#### [MODIFY] backend/routers/spotify_auth.py
- Change the `scope` variable to include `user-top-read` (e.g., `"user-read-private user-read-email user-top-read"`).
- In the `/callback` route, extract the `access_token` from `token_resp.json()`.
- Append the `spotify_token` to the redirect URL:
  `return RedirectResponse(f"{settings.frontend_url}/#/auth/callback?token={encoded_jwt}&spotify_token={access_token}")`

---

### 2. Frontend: Authentication State
#### [MODIFY] frontend/src/lib/stores.js
- Add a new persistent store (or just `localStorage` wrapper) for `spotifyAccessToken`. It will expire automatically according to Spotify's 1-hour limit, but it's enough for an active session.

#### [MODIFY] frontend/src/routes/public/AuthCallback.svelte (or wherever callback is handled)
- Parse `spotify_token` from the URL parameters.
- Save it to the `spotifyAccessToken` store.

---

### 3. Frontend: Top Artists Integration
#### [MODIFY] frontend/src/routes/public/Home.svelte
- **Data Fetching:** If `spotifyAccessToken` is available, make a `fetch()` request to `https://api.spotify.com/v1/me/top/artists?limit=50` using the token in the `Authorization: Bearer` header.
- **Intersection:** Map the response to an array of Spotify IDs (`topSpotifyIds`).
  Filter our local `artists` array: 
  `let userTopArtists = artists.filter(a => topSpotifyIds.includes(a.spotify_id))`
- **Sorting:** Sort `userTopArtists` to match the rank order provided by the Spotify API response.
- **UI:** Add a new section above the main artist grid:
  ```html
  {#if userTopArtists.length > 0}
    <div class="mb-12">
      <h2 class="text-2xl font-bold mb-4">Your Top Artists</h2>
      <div class="artist-grid ...">
        <!-- Render cards for userTopArtists -->
      </div>
    </div>
    <h2 class="text-2xl font-bold mb-4">All Detected Artists</h2>
  {/if}
  ```
- **Error Handling:** If the Spotify fetch returns 401 (token expired), quietly ignore it or clear the `spotifyAccessToken` store.

---

## Verification Plan
1. Check the Spotify Developer Dashboard to ensure the Client ID has access to the `user-top-read` scope (standard users can grant this).
2. Log in as a public user in the frontend.
3. Verify the browser receives both the internal token and the `spotify_token`.
4. Observe the `Home.svelte` page successfully fetching the top artists from Spotify and displaying the intersected matches gracefully.
