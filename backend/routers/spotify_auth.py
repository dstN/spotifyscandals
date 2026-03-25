from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
import httpx
import jwt
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from config import Settings, get_settings
import urllib.parse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public/auth/spotify", tags=["Spotify Auth"])

# ── CSRF State Store ──
# Server-side state store for OAuth CSRF protection.
# This is the standard approach used by most OAuth libraries (Django social-auth,
# Flask-Dance, etc.) — the state token is stored server-side and validated on
# callback. Works regardless of proxy/cookie configuration.
# For multi-instance deployments, replace with Redis or database storage.
_pending_states: dict[str, float] = {}
_MAX_STATES = 1000  # prevent unbounded growth


def _cleanup_expired_states():
    """Remove expired state tokens."""
    now = time.time()
    expired = [k for k, v in _pending_states.items() if v < now]
    for k in expired:
        del _pending_states[k]


@router.get("/login")
def login_with_spotify(request: Request, settings: Settings = Depends(get_settings)):
    """Redirect user to Spotify for OAuth login."""
    _cleanup_expired_states()

    # Enforce a cap to prevent memory abuse
    if len(_pending_states) >= _MAX_STATES:
        log.warning("OAuth state store full (%d entries), pruning oldest", len(_pending_states))
        oldest = sorted(_pending_states, key=_pending_states.get)[:len(_pending_states) // 2]
        for k in oldest:
            del _pending_states[k]

    state = secrets.token_urlsafe(32)
    _pending_states[state] = time.time() + 600  # 10 min TTL

    scope = "user-read-private user-read-email user-top-read"
    query_params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": scope,
        "show_dialog": "false",
        "state": state,
    }
    url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(query_params)}"
    return RedirectResponse(url)


@router.get("/callback")
async def spotify_callback(
    request: Request,
    code: str = None,
    error: str = None,
    state: str = None,
    settings: Settings = Depends(get_settings),
):
    """Handle the OAuth callback from Spotify."""
    if error:
        return RedirectResponse(f"{settings.frontend_url}/auth/error?message={error}")

    # Validate CSRF state token
    if not state or state not in _pending_states or _pending_states[state] < time.time():
        log.warning("OAuth CSRF validation failed (state %s)", "missing" if not state else "invalid/expired")
        return RedirectResponse(f"{settings.frontend_url}/auth/error?message=Invalid_state")
    del _pending_states[state]  # one-time use

    if not code:
        return RedirectResponse(f"{settings.frontend_url}/auth/error?message=Missing_code")
        
    # Exchange code for token
    token_url = "https://accounts.spotify.com/api/token"
    auth_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.spotify_redirect_uri,
        "client_id": settings.spotify_client_id,
        "client_secret": settings.spotify_client_secret,
    }
    
    async with httpx.AsyncClient() as client:
        # Request access token
        token_resp = await client.post(token_url, data=auth_data)
        if token_resp.status_code != 200:
            return RedirectResponse(f"{settings.frontend_url}/auth/error?message=Token_exchange_failed")
            
        token_info = token_resp.json()
        access_token = token_info.get("access_token")
        
        # Get user profile
        user_resp = await client.get(
            "https://api.spotify.com/v1/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_resp.status_code != 200:
            return RedirectResponse(f"{settings.frontend_url}/auth/error?message=Profile_fetch_failed")
            
        user_data = user_resp.json()
        spotify_id = user_data.get("id")
        display_name = user_data.get("display_name")
        images = user_data.get("images", [])
        profile_image = images[0].get("url") if images else None
        
    # Generate our own internal JWT for the public user session
    expires_delta = timedelta(days=30)
    expire = datetime.now(timezone.utc) + expires_delta
    
    to_encode = {
        "sub": spotify_id,
        "name": display_name or spotify_id,
        "image": profile_image,
        "role": "public_user",
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")
    
    # Redirect back to frontend with tokens in URL fragment (not query params)
    # Fragments are not sent to servers and not included in Referer headers
    return RedirectResponse(f"{settings.frontend_url}/auth/callback#token={encoded_jwt}&spotify_token={access_token}")
