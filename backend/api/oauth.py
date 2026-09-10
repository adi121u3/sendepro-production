"""Secure browser OAuth connection flow for Google and Microsoft mailboxes."""
import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Account, AccountCredential, ActivityLog
from backend.security.auth import get_current_admin
from backend.security.encryption import encrypt_credential

router = APIRouter(prefix="/api/oauth", tags=["oauth"])
MICROSOFT_SCOPES = "openid offline_access email profile https://outlook.office.com/SMTP.Send https://outlook.office.com/IMAP.AccessAsUser.All"
GOOGLE_SCOPES = "openid email profile https://mail.google.com/"

class OAuthStart(BaseModel):
    provider: str

def _provider(value: str) -> str:
    value = (value or "").strip().lower()
    if value in {"outlook", "microsoft"}: return "microsoft"
    if value in {"gmail", "google"}: return "google"
    raise HTTPException(status_code=400, detail="Provider must be google or microsoft.")

def _env(provider: str, suffix: str) -> str:
    name = f"{provider.upper()}_{suffix}"
    value = os.getenv(name, "").strip()
    if not value: raise HTTPException(status_code=503, detail=f"{name} is not configured.")
    return value

def _redirect_uri(provider: str) -> str:
    name = "OAUTH_REDIRECT_URI" if provider == "google" else "MICROSOFT_REDIRECT_URI"
    value = os.getenv(name, "").strip()
    if not value: raise HTTPException(status_code=503, detail=f"{name} is not configured.")
    return value

def _authority() -> str:
    tenant = os.getenv("MICROSOFT_TENANT_ID", "common").strip() or "common"
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"

def _state_secret() -> bytes:
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32: raise HTTPException(status_code=503, detail="SECRET_KEY must be configured with at least 32 characters.")
    return secret.encode()

def _make_state(provider: str) -> str:
    payload = json.dumps({"provider": provider, "exp": int(time.time()) + 600, "nonce": secrets.token_urlsafe(24)}, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(hmac.new(_state_secret(), encoded.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{encoded}.{signature}"

def _read_state(state: str) -> str:
    try:
        encoded, signature = state.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(_state_secret(), encoded.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(signature, expected): raise ValueError("signature")
        data = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(data["exp"]) < int(time.time()): raise ValueError("expired")
        return _provider(data["provider"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="OAuth session is invalid or expired. Start sign-in again.") from exc

def _decode_claims(token: str) -> dict:
    try:
        part = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
    except Exception: return {}

@router.post("/start")
def oauth_start(payload: OAuthStart, _admin: str = Depends(get_current_admin)):
    provider = _provider(payload.provider)
    redirect_uri = _redirect_uri(provider)
    if provider == "google":
        endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {"client_id": _env(provider, "CLIENT_ID"), "redirect_uri": redirect_uri, "response_type": "code", "scope": GOOGLE_SCOPES, "access_type": "offline", "prompt": "consent", "state": _make_state(provider)}
    else:
        endpoint = _authority() + "/authorize"
        params = {"client_id": _env(provider, "CLIENT_ID"), "redirect_uri": redirect_uri, "response_type": "code", "response_mode": "query", "scope": MICROSOFT_SCOPES, "prompt": "select_account", "state": _make_state(provider)}
    return {"authorize_url": endpoint + "?" + urlencode(params)}

@router.get("/callback")
def oauth_callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    provider = _read_state(state)
    redirect_uri = _redirect_uri(provider)
    token_url = "https://oauth2.googleapis.com/token" if provider == "google" else _authority() + "/token"
    data = {"code": code, "client_id": _env(provider, "CLIENT_ID"), "client_secret": _env(provider, "CLIENT_SECRET"), "redirect_uri": redirect_uri, "grant_type": "authorization_code"}
    if provider == "microsoft": data["scope"] = MICROSOFT_SCOPES
    try:
        response = requests.post(token_url, data=data, timeout=20)
        response.raise_for_status()
        tokens = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise HTTPException(status_code=400, detail="OAuth token exchange failed. Check provider configuration and try again.") from exc
    access_token, refresh_token = tokens.get("access_token", ""), tokens.get("refresh_token", "")
    if not access_token: raise HTTPException(status_code=400, detail="OAuth provider returned no access token.")
    claims = _decode_claims(tokens.get("id_token", ""))
    email = claims.get("email") or claims.get("preferred_username") or claims.get("upn") or ""
    name = claims.get("name") or email
    if provider == "google" and not email:
        try:
            profile_response = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"}, timeout=20)
            profile_response.raise_for_status(); profile = profile_response.json()
            email, name = profile.get("email", ""), profile.get("name", "") or profile.get("email", "")
        except (requests.RequestException, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Could not retrieve the Google account profile.") from exc
    if not email: raise HTTPException(status_code=400, detail="The provider did not return an email address.")
    account = db.query(Account).filter(Account.email == email, Account.provider == provider).first()
    if not account:
        account = Account(provider=provider, name=name, email=email, from_name=name, enabled=True, daily_limit=500, status="active", smtp_host="smtp.gmail.com" if provider == "google" else "smtp.office365.com", smtp_port=587, smtp_security="starttls", smtp_username=email, imap_host="imap.gmail.com" if provider == "google" else "outlook.office365.com", imap_port=993, imap_security="ssl", imap_username=email)
        db.add(account); db.flush()
    else:
        account.name, account.status, account.updated_at = name, "active", datetime.utcnow()
        account.smtp_host = account.smtp_host or ("smtp.gmail.com" if provider == "google" else "smtp.office365.com")
        account.smtp_port, account.smtp_security, account.smtp_username = account.smtp_port or 587, account.smtp_security or "starttls", account.smtp_username or email
        account.imap_host = account.imap_host or ("imap.gmail.com" if provider == "google" else "outlook.office365.com")
        account.imap_port, account.imap_security, account.imap_username = account.imap_port or 993, account.imap_security or "ssl", account.imap_username or email
    credential = db.query(AccountCredential).filter(AccountCredential.account_id == account.id).first() or AccountCredential(account_id=account.id)
    credential.oauth_access_token_enc = encrypt_credential(access_token)
    if refresh_token: credential.oauth_refresh_token_enc = encrypt_credential(refresh_token)
    credential.oauth_token_expires_at = datetime.utcnow() + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    db.add(credential); db.add(ActivityLog(event_type="oauth_connected", severity="info", message=f"OAuth connected for {email} via {provider}.", entity_id=account.id)); db.commit()
    safe_email, safe_provider = html.escape(email), html.escape(provider.title())
    return HTMLResponse(f"""<!doctype html><html><head><meta charset='utf-8'><title>Account connected</title></head><body style='font-family:system-ui;background:#020617;color:#f8fafc;display:grid;place-items:center;height:100vh;margin:0'><main style='background:#0f172a;padding:32px;border-radius:16px;text-align:center'><h2>Account connected</h2><p>{safe_email} is connected through {safe_provider}.</p><p>You may close this window.</p></main><script>if(window.opener){{window.opener.postMessage({{type:'esp-oauth-complete'}},window.location.origin);setTimeout(()=>window.close(),800);}}</script></body></html>""")
