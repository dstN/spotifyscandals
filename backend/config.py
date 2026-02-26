"""
Application configuration.
Loads environment variables via pydantic-settings for type-safe access.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    # ─── Spotify Web API ───
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8001/api/public/auth/spotify/callback"
    frontend_url: str = "http://localhost:5173"

    # ─── Google Gemini Pro ───
    gemini_api_key: str = ""

    # ─── Auth (Admin User & JWT) ───
    admin_username: str = "admin"
    admin_password: str = "secret"
    jwt_secret: str = "super_secret_jwt_key_change_in_production"

    # ─── Database ───
    database_url: str = "sqlite:///./skandal_tracker.db"

    # ─── CORS ───
    cors_origins: str = "http://localhost:5173"

    # ─── Server ───
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
