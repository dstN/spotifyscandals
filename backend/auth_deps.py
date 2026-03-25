from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from config import get_settings

security = HTTPBearer()

def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency to check if the incoming request has a valid admin JWT token.
    Throws 401 if invalid/missing.
    """
    settings = get_settings()
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        # Require explicit admin role claim — reject any other role
        if payload.get("role") != "admin":
            raise HTTPException(status_code=401, detail="Not an admin token")
        if payload.get("sub") != settings.admin_username:
            raise HTTPException(status_code=401, detail="Invalid admin token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return payload.get("sub")


def get_current_public_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency to extract the Spotify user ID from a public user token.
    Throws 401 if missing or invalid.
    """
    settings = get_settings()
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("role") != "public_user":
            raise HTTPException(status_code=401, detail="Not a public user token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return payload.get("sub")


from fastapi import Request

def get_optional_public_user(request: Request):
    """
    Extracts the Spotify user ID if a valid token is present in the Authorization header.
    Returns None if missing or invalid, does not throw.
    """
    settings = get_settings()
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
        
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        if payload.get("role") == "public_user":
            return payload.get("sub")
    except Exception:
        pass
        
    return None
