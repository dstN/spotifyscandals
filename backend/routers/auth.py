from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from config import Settings, get_settings
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# ─── Login Rate Limiting ───
_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_LOGIN_ATTEMPTS = 5
_LOGIN_WINDOW = 300  # 5 minutes


def _check_login_rate_limit(request: Request):
    """Raise 429 if too many login attempts from this IP."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < _LOGIN_WINDOW]
    if len(_login_attempts[ip]) >= _MAX_LOGIN_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    _login_attempts[ip].append(now)


@router.post("/login", response_model=TokenResponse)
def login(creds: LoginRequest, request: Request, settings: Settings = Depends(get_settings)):

    # Rate-limit login attempts per IP
    _check_login_rate_limit(request)

    # Validate credentials using bcrypt hash comparison
    if not settings.admin_password_hash:
        logger.error("ADMIN_PASSWORD_HASH is not configured — login is disabled")
        raise HTTPException(status_code=503, detail="Admin login is not configured")

    if creds.username != settings.admin_username or not bcrypt.checkpw(creds.password.encode(), settings.admin_password_hash.encode()):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    # Generate JWT with explicit role claim
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode = {
        "sub": settings.admin_username,
        "role": "admin",
        "exp": expire,
    }
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")

    return {"access_token": encoded_jwt, "token_type": "bearer"}
