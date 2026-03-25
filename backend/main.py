"""
Spotify Skandal Tracker — FastAPI Application Entry Point

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
import asyncio

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


# ─── Auto-Scan Top 50 (background scheduler) ───
_auto_scan_task: asyncio.Task | None = None

async def _auto_scan_loop():
    """Run the Top 50 auto-scan every 4 weeks."""
    from services.tasks import run_top50_auto_scan
    INTERVAL = 4 * 7 * 24 * 60 * 60  # 4 weeks in seconds
    while True:
        await asyncio.sleep(INTERVAL)
        try:
            await run_top50_auto_scan()
        except Exception as e:
            print(f"[AutoScan] Scheduled scan failed: {e}")


@app.on_event("startup")
async def start_auto_scan_scheduler():
    global _auto_scan_task
    if get_settings().auto_scan_enabled:
        _auto_scan_task = asyncio.create_task(_auto_scan_loop())
        print("[OK] Auto-scan scheduler started (every 4 weeks)")


@app.on_event("shutdown")
async def stop_auto_scan_scheduler():
    global _auto_scan_task
    if _auto_scan_task:
        _auto_scan_task.cancel()


# ─── Admin: Manual trigger for Top 50 auto-scan ───
from fastapi import Depends
from auth_deps import require_admin

@app.post("/api/admin/trigger-auto-scan")
async def trigger_auto_scan(admin: str = Depends(require_admin)):
    """Manually trigger the Top 50 auto-scan pipeline."""
    from services.tasks import run_top50_auto_scan
    try:
        await run_top50_auto_scan()
        return {"message": "Auto-scan triggered successfully"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


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
        file_path = os.path.join(dist_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))
