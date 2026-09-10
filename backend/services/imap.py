"""Real IMAP mailbox access with header-first fetching and UID-based actions."""
import email
import imaplib
import re
import ssl
import os
import requests
from email.header import decode_header, make_header
from email.utils import parseaddr

def _decode(value: str | None) -> str:
    try: return str(make_header(decode_header(value or "")))
    except Exception: return value or ""

def refresh_oauth_token(provider: str, refresh_token: str) -> tuple[str, int]:
    provider = provider.lower()
    if provider == "google":
        url = "https://oauth2.googleapis.com/token"
        data = {"client_id": os.getenv("GOOGLE_CLIENT_ID", ""), "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""), "refresh_token": refresh_token, "grant_type": "refresh_token"}
    else:
        tenant = os.getenv("MICROSOFT_TENANT_ID", "common") or "common"
        url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
        data = {"client_id": os.getenv("MICROSOFT_CLIENT_ID", ""), "client_secret": os.getenv("MICROSOFT_CLIENT_SECRET", ""), "refresh_token": refresh_token, "grant_type": "refresh_token", "scope": "openid offline_access email profile https://outlook.office.com/SMTP.Send https://outlook.office.com/IMAP.AccessAsUser.All"}
    response = requests.post(url, data=data, timeout=20); response.raise_for_status()
    payload = response.json()
    return payload["access_token"], int(payload.get("expires_in", 3600))

def connect(account, password: str = "", access_token: str = ""):
    if not account.imap_host:
        raise ValueError("Incoming mail is not configured for this account.")
    if not password and not access_token:
        raise ValueError("An IMAP password is not stored. Re-save the account password.")
    host, port = account.imap_host.strip(), int(account.imap_port or 993)
    security = (account.imap_security or "ssl").lower()
    if security == "ssl" or port == 993:
        client = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=20)
    else:
        client = imaplib.IMAP4(host, port, timeout=20)
        if security == "starttls": client.starttls(ssl_context=ssl.create_default_context())
    username = account.imap_username or account.email
    if access_token:
        auth = f"user={username}\x01auth=Bearer {access_token}\x01\x01".encode()
        client.authenticate("XOAUTH2", lambda _: auth)
    else:
        client.login(username, password)
    return client

def list_messages(client, folder="INBOX", limit=50, offset=0):
    status, _ = client.select(folder, readonly=True)
    if status != "OK": raise ValueError(f"Cannot open IMAP folder {folder}.")
    status, data = client.uid("search", None, "ALL")
    if status != "OK": raise ValueError("Unable to search the mailbox.")
    uids = list(reversed(data[0].split()))[offset:offset + limit]
    messages = []
    if not uids: return messages
    status, parts = client.uid("fetch", b",".join(uids), "(UID FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO REPLY-TO SUBJECT DATE MESSAGE-ID)])")
    if status != "OK": raise ValueError("Unable to fetch message headers.")
    for part in parts:
        if not isinstance(part, tuple): continue
        meta, raw = part[0], part[1]
        uid_match = re.search(rb"UID\s+(\d+)", meta)
        if not uid_match: continue
        msg = email.message_from_bytes(raw)
        from_name, from_email = parseaddr(_decode(msg.get("From")))
        _, reply_email = parseaddr(_decode(msg.get("Reply-To")))
        messages.append({"uid": uid_match.group(1).decode(), "from_name": from_name, "from_email": from_email, "reply_to": reply_email or from_email, "subject": _decode(msg.get("Subject")), "date": _decode(msg.get("Date")), "message_id": msg.get("Message-ID", ""), "unread": b"\\Seen" not in meta})
    return messages

def get_message(client, uid: str, folder="INBOX"):
    client.select(folder, readonly=False)
    status, parts = client.uid("fetch", uid, "(BODY.PEEK[])")
    if status != "OK": raise ValueError("Message could not be fetched.")
    raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
    if raw is None: raise ValueError("Message was not found.")
    msg = email.message_from_bytes(raw)
    text, html_body = "", ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_disposition() == "attachment": continue
        payload = part.get_payload(decode=True) or b""
        content = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if part.get_content_type() == "text/plain" and not text: text = content
        if part.get_content_type() == "text/html" and not html_body: html_body = content
    from_name, from_email = parseaddr(_decode(msg.get("From")))
    _, reply_email = parseaddr(_decode(msg.get("Reply-To")))
    client.uid("store", uid, "+FLAGS", "(\\Seen)")
    return {"uid": uid, "from_name": from_name, "from_email": from_email, "reply_to": reply_email or from_email, "to": _decode(msg.get("To")), "subject": _decode(msg.get("Subject")), "date": _decode(msg.get("Date")), "message_id": msg.get("Message-ID", ""), "text": text, "html": html_body}

def bulk_action(client, uids: list[str], action: str, folder="INBOX"):
    client.select(folder, readonly=False)
    sequence = ",".join(uid for uid in uids if re.fullmatch(r"\d+", uid))
    if not sequence: raise ValueError("No valid messages selected.")
    if action == "read": client.uid("store", sequence, "+FLAGS", "(\\Seen)")
    elif action == "unread": client.uid("store", sequence, "-FLAGS", "(\\Seen)")
    elif action == "delete": client.uid("store", sequence, "+FLAGS", "(\\Deleted)"); client.expunge()
    else: raise ValueError("Action must be read, unread, or delete.")
