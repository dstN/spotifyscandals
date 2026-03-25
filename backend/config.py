"""
Application configuration.
Loads environment variables via pydantic-settings for type-safe access.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from functools import lru_cache
import os
import secrets
from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    # ─── Spotify Web API ───
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8001/api/public/auth/spotify/callback"
    frontend_url: str = "http://127.0.0.1:5173"

    # ─── Google Gemini Pro ───
    gemini_api_key: str = ""

    # ─── Gemini Rate Limits (Free Tier defaults) ───
    scanner_mode: str = "free_tier"          # "free_tier" or "unlimited"
    gemini_model_rpm: int = 15               # Requests per minute (model calls)
    gemini_model_rpd: int = 1500             # Requests per day (model calls)
    gemini_search_rpd: int = 1500            # Requests per day (Google Search grounding)

    # ─── Auth (Admin User & JWT) ───
    admin_username: str = "admin"
    # Store a bcrypt hash — generate with: python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
    admin_password_hash: str = ""
    jwt_secret: str = ""

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def set_jwt_secret(cls, v: str) -> str:
        """Auto-generate a random JWT secret if not explicitly set or too weak."""
        if not v or len(v) < 32 or "change" in v.lower():
            return secrets.token_urlsafe(32)
        return v

    # ─── Database ───
    database_url: str = Field(default="sqlite:///./spotiscandals.db")

    @field_validator("database_url")
    @classmethod
    def make_absolute(cls, v: str) -> str:
        """Ensure database_url is absolute if it's a relative sqlite path."""
        if v.startswith("sqlite:///./"):
            db_name = v.replace("sqlite:///./", "")
            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), db_name))
            return f"sqlite:///{db_path}"
        return v

    # ─── CORS ───
    cors_origins: str = "http://localhost:5173"

    # ─── Server ───
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
