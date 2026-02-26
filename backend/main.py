"""
Spotify Skandal Tracker — FastAPI Application Entry Point

Registers all routers, configures CORS, and initializes the database on startup.
Run with: uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings
from database import init_db

# ─── Import routers ───
from routers.playlists import router as playlists_router
from routers.artists import router as artists_router
from routers.scandals import router as scandals_router
from routers.auth import router as auth_router
from routers.spotify_auth import router as spotify_auth_router
from routers.community import router as community_router

# ─── App initialization ───
app = FastAPI(
    title="Spotify Skandal Tracker",
    description="Discover and track artist scandals from Spotify playlists using AI",
    version="1.0.0",
)

# ─── CORS ───
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register routers ───
app.include_router(auth_router)
app.include_router(playlists_router)
app.include_router(artists_router)
app.include_router(scandals_router)
app.include_router(spotify_auth_router)
app.include_router(community_router)


# ─── Startup event: create database tables ───
@app.on_event("startup")
def on_startup():
    """Create all database tables if they don't exist."""
    init_db()
    print("[OK] Database initialized")


# ─── Health check ───
@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Spotify Skandal Tracker"}
