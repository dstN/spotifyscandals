from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta, timezone
from config import get_settings

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/login", response_model=TokenResponse)
def login(creds: LoginRequest):
    settings = get_settings()
    
    # Simple direct string match against config for the single admin user
    if creds.username != settings.admin_username or creds.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
        
    # Generate JWT
    expires_delta = timedelta(hours=24)
    expire = datetime.now(timezone.utc) + expires_delta
    
    to_encode = {
        "sub": settings.admin_username,
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")
    
    return {"access_token": encoded_jwt, "token_type": "bearer"}
