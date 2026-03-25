"""
spotifyscandals — FastAPI Application Entry Point

Registers all routers, configures CORS, and initializes the database on startup.
Run with: uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from config import get_settings
from database import init_db
import os
import logging
from contextlib import asynccontextmanager

# ─── Configure structured logging ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Import routers ───
from routers.playlists import router as playlists_router
from routers.artists import router as artists_router
from routers.scandals import router as scandals_router
from routers.auth import router as auth_router
from routers.spotify_auth import router as spotify_auth_router
from routers.community import router as community_router


# ─── Lifespan context manager ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic for the application."""
    init_db()
    logger.info("Database initialized")
    yield


# ─── App initialization ───
app = FastAPI(
    title="spotifyscandals",
    description="Discover and track artist scandals from Spotify playlists using AI",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Security Headers Middleware ───
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Skip CSP for API docs (Swagger UI needs inline scripts + CDN resources)
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' https://i.scdn.co data:; "
                "connect-src 'self' https://api.spotify.com; "
                "font-src 'self'; "
                "frame-ancestors 'none'"
            )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ─── CORS ───
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─── Register routers ───
app.include_router(auth_router)
app.include_router(playlists_router)
app.include_router(artists_router)
app.include_router(scandals_router)
app.include_router(spotify_auth_router)
app.include_router(community_router)


# ─── Health check ───
@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Spotify Skandal Tracker"}


# ─── SPA static files & catch-all ───
dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.isdir(dist_dir):
    # Serve static assets (JS, CSS, images) from the built frontend
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA index.html for all non-API routes (path-based routing)."""
        file_path = os.path.realpath(os.path.join(dist_dir, full_path))
        # Prevent path traversal — resolved path must stay within dist_dir
        if not file_path.startswith(os.path.realpath(dist_dir)):
            return FileResponse(os.path.join(dist_dir, "index.html"))
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))
