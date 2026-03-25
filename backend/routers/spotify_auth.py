from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
import httpx
import jwt
from datetime import datetime, timedelta, timezone
from config import get_settings
import urllib.parse

router = APIRouter(prefix="/api/public/auth/spotify", tags=["Spotify Auth"])

@router.get("/login")
def login_with_spotify():
    """Redirect user to Spotify for OAuth login."""
    settings = get_settings()
    scope = "user-read-private user-read-email user-top-read"
    query_params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": scope,
        "show_dialog": "false",
    }
    url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(query_params)}"
    return RedirectResponse(url)

@router.get("/callback")
async def spotify_callback(code: str = None, error: str = None):
    """Handle the OAuth callback from Spotify."""
    settings = get_settings()
    
    if error:
        return RedirectResponse(f"{settings.frontend_url}/auth/error?message={error}")
    
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
    
    # Redirect back to frontend with both internal JWT and Spotify access token
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?token={encoded_jwt}&spotify_token={access_token}")
