import os
import hmac
import hashlib
import json
import base64
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Environment-driven secret key
def _get_jwt_secret() -> bytes:
    secret = os.getenv("SECRET_KEY") or os.getenv("CREDENTIAL_SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY must be configured with a random value of at least 32 characters.")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters.")
    return secret.encode("utf-8")

def _admin_credentials() -> tuple[str, str]:
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not username or not password or len(password) < 12:
        raise RuntimeError("ADMIN_USERNAME and ADMIN_PASSWORD (12+ characters) must be configured.")
    return username, password

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str

def create_access_token(username: str, expires_delta_seconds: int = 86400) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_delta_seconds
    }
    
    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    
    b64_header = base64.urlsafe_b64encode(header_json).rstrip(b"=").decode("utf-8")
    b64_payload = base64.urlsafe_b64encode(payload_json).rstrip(b"=").decode("utf-8")
    
    signing_input = f"{b64_header}.{b64_payload}".encode("utf-8")
    signature = hmac.new(_get_jwt_secret(), signing_input, hashlib.sha256).digest()
    b64_sig = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("utf-8")
    
    return f"{b64_header}.{b64_payload}.{b64_sig}"

def verify_access_token(token: str) -> Optional[str]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        b64_header, b64_payload, b64_sig = parts
        
        signing_input = f"{b64_header}.{b64_payload}".encode("utf-8")
        expected_sig = hmac.new(_get_jwt_secret(), signing_input, hashlib.sha256).digest()
        expected_b64_sig = base64.urlsafe_b64encode(expected_sig).rstrip(b"=").decode("utf-8")
        
        if not hmac.compare_digest(b64_sig, expected_b64_sig):
            return None
            
        padding = "=" * (-len(b64_payload) % 4)
        payload_json = base64.urlsafe_b64decode(b64_payload + padding).decode("utf-8")
        payload = json.loads(payload_json)
        
        if payload.get("exp", 0) < int(time.time()):
            return None
            
        return payload.get("sub")
    except Exception:
        return None

def get_current_admin(authorization: Optional[str] = Header(None)) -> str:
    """Dependency to enforce JWT authentication on administrative endpoints."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token = parts[1]
    username = verify_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    """Authenticate administrator and return a signed JWT token."""
    admin_user, admin_pass = _admin_credentials()
    if not hmac.compare_digest(payload.username, admin_user) or not hmac.compare_digest(payload.password, admin_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
        
    token = create_access_token(payload.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": payload.username
    }

@router.get("/verify")
def verify_token_endpoint(username: str = Depends(get_current_admin)):
    return {"status": "authenticated", "username": username}
