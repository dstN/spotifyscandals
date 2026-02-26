"""
Spotify Web API integration service.

Handles:
  1. Client Credentials authentication (no user login needed)
  2. Fetching playlist tracks
  3. Extracting unique artist data (name, spotify_id, image)
"""

import httpx
import re
from config import get_settings

# ─── Spotify API endpoints ───
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


async def get_spotify_token() -> str:
    """
    Obtain an access token using the Client Credentials flow.
    This doesn't require user login — suitable for public playlist data.
    """
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SPOTIFY_AUTH_URL,
            data={"grant_type": "client_credentials"},
            auth=(settings.spotify_client_id, settings.spotify_client_secret),
        )
        response.raise_for_status()
        return response.json()["access_token"]


def extract_playlist_id(url: str) -> str:
    """
    Extract the playlist ID from various Spotify URL formats:
      - https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M
      - spotify:playlist:37i9dQZF1DXcBWIGoYBM5M
      - 37i9dQZF1DXcBWIGoYBM5M (raw ID)
    """
    # Try full URL pattern
    match = re.search(r"playlist[/:]([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    # Assume raw playlist ID
    return url.strip()


async def fetch_playlist(playlist_url: str) -> dict:
    """
    Fetch a Spotify playlist and return its metadata + all unique artists.

    Returns:
        {
            "playlist_name": str,
            "artists": [
                {"name": str, "spotify_id": str, "image_url": str | None},
                ...
            ]
        }

    NOTE: We deliberately avoid passing a `fields` filter to the paginated
    /playlists/{id}/tracks endpoint. Spotify embeds the `fields` query param
    into the `next` pagination URL. If those field selectors use playlist-level
    paths (e.g. `tracks.items(...)`) they become invalid for the /tracks
    sub-endpoint, causing page 2+ to return `{}` silently — dropping all
    artists beyond the first 100 tracks.
    """
    token = await get_spotify_token()
    playlist_id = extract_playlist_id(playlist_url)

    headers = {"Authorization": f"Bearer {token}"}
    artists_map: dict[str, dict] = {}  # spotify_id → artist data

    async with httpx.AsyncClient() as client:
        # ── Step 1: fetch playlist name only (minimal, no track data) ──────────
        playlist_resp = await client.get(
            f"{SPOTIFY_API_BASE}/playlists/{playlist_id}",
            headers=headers,
            params={"fields": "name"},
        )
        playlist_resp.raise_for_status()
        playlist_name = playlist_resp.json().get("name", "Unknown Playlist")

        # ── Step 2: paginate /tracks directly so `next` URLs stay clean ────────
        # Using `fields` scoped only for the /tracks sub-endpoint ensures the
        # embedded `next` URL works correctly on every subsequent page.
        tracks_resp = await client.get(
            f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks",
            headers=headers,
            params={
                "limit": 100,
                "fields": "items(track(artists)),next,total",
            },
        )
        tracks_resp.raise_for_status()
        tracks_data = tracks_resp.json()
        _extract_artists_from_items(tracks_data.get("items", []), artists_map)

        # Handle pagination — playlists can have 100+ tracks
        next_url = tracks_data.get("next")
        while next_url:
            next_resp = await client.get(next_url, headers=headers)
            next_resp.raise_for_status()
            next_data = next_resp.json()
            _extract_artists_from_items(next_data.get("items", []), artists_map)
            next_url = next_data.get("next")

    # Now fetch artist images (batch request, max 50 at a time)
    artist_ids = list(artists_map.keys())
    if artist_ids:
        async with httpx.AsyncClient() as client:
            for i in range(0, len(artist_ids), 50):
                batch = artist_ids[i:i + 50]
                artists_resp = await client.get(
                    f"{SPOTIFY_API_BASE}/artists",
                    headers=headers,
                    params={"ids": ",".join(batch)},
                )
                if artists_resp.status_code == 200:
                    for artist_data in artists_resp.json().get("artists", []):
                        if artist_data and artist_data["id"] in artists_map:
                            images = artist_data.get("images", [])
                            if images:
                                artists_map[artist_data["id"]]["image_url"] = images[0]["url"]

    return {
        "playlist_name": playlist_name,
        "artists": list(artists_map.values()),
    }


def _extract_artists_from_items(items: list, artists_map: dict):
    """
    Extract unique artists from a page of playlist track items.
    Deduplicates by Spotify artist ID.
    """
    for item in items:
        track = item.get("track")
        if not track:
            continue
        for artist in track.get("artists", []):
            artist_id = artist.get("id")
            if artist_id and artist_id not in artists_map:
                artists_map[artist_id] = {
                    "name": artist.get("name", "Unknown"),
                    "spotify_id": artist_id,
                    "image_url": None,
                }
