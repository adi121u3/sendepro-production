from datetime import datetime, timedelta
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Account
from backend.security.encryption import decrypt_credential, encrypt_credential
from backend.services.imap import connect, list_messages, get_message, bulk_action, refresh_oauth_token

router = APIRouter(prefix="/api/inbox", tags=["inbox"])
class BulkAction(BaseModel):
    account_id: int
    uids: list[str] = Field(min_length=1, max_length=200)
    action: str
    folder: str = "INBOX"

def _client(db, account_id):
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account: raise HTTPException(404, "Account not found.")
    if account.provider == "zeptomail": raise HTTPException(400, "ZeptoMail is send-only and does not provide an IMAP mailbox. Configure a separate incoming-mail account.")
    credential = account.credential
    password = decrypt_credential(credential.smtp_password_enc) if credential and credential.smtp_password_enc else ""
    access_token = decrypt_credential(credential.oauth_access_token_enc) if credential and credential.oauth_access_token_enc else ""
    provider = (account.provider or "").lower()
    if provider in {"google", "microsoft", "outlook"} and credential:
        expires = credential.oauth_token_expires_at
        if not access_token or (expires and expires <= datetime.utcnow() + timedelta(seconds=60)):
            refresh_token = decrypt_credential(credential.oauth_refresh_token_enc) if credential.oauth_refresh_token_enc else ""
            if not refresh_token: raise HTTPException(400, "OAuth session expired. Reconnect this account.")
            try:
                access_token, expires_in = refresh_oauth_token(provider, refresh_token)
                credential.oauth_access_token_enc = encrypt_credential(access_token)
                credential.oauth_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                db.commit()
            except Exception as exc: raise HTTPException(400, "OAuth refresh failed. Reconnect this account and approve incoming-mail access.") from exc
    try: return connect(account, password=password, access_token=access_token)
    except Exception as exc: raise HTTPException(400, f"IMAP connection failed: {exc}") from exc

def _folder(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9 _./-]{1,100}", value or ""):
        raise HTTPException(400, "Invalid IMAP folder name.")
    return value

@router.get("/messages")
def messages(account_id: int, folder: str = "INBOX", limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    client = _client(db, account_id)
    try: return list_messages(client, _folder(folder), limit, offset)
    finally: client.logout()

@router.get("/messages/{uid}")
def message(uid: str, account_id: int, folder: str = "INBOX", db: Session = Depends(get_db)):
    if not uid.isdigit(): raise HTTPException(400, "Invalid message UID.")
    client = _client(db, account_id)
    try: return get_message(client, uid, _folder(folder))
    finally: client.logout()

@router.post("/bulk")
def bulk(payload: BulkAction, db: Session = Depends(get_db)):
    client = _client(db, payload.account_id)
    try: bulk_action(client, payload.uids, payload.action, _folder(payload.folder)); return {"status": "success", "count": len(payload.uids)}
    finally: client.logout()
