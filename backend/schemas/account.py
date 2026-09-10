from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class AccountCreate(BaseModel):
    provider: str # smtp, emailsrvr/rackspace, bell, microsoft, zeptomail, google
    name: str
    email: str
    from_name: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = 587
    smtp_security: Optional[str] = "starttls"
    smtp_username: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = 993
    imap_security: Optional[str] = "ssl"
    imap_username: Optional[str] = None
    enabled: Optional[bool] = True
    daily_limit: Optional[int] = 500
    smtp_password: Optional[str] = None
    zeptomail_api_key: Optional[str] = None

class AccountUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    from_name: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_security: Optional[str] = None
    smtp_username: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_security: Optional[str] = None
    imap_username: Optional[str] = None
    enabled: Optional[bool] = None
    daily_limit: Optional[int] = None
    status: Optional[str] = None
    smtp_password: Optional[str] = None
    zeptomail_api_key: Optional[str] = None

class AccountResponse(BaseModel):
    id: int
    provider: str
    name: str
    email: str
    from_name: Optional[str]
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_security: Optional[str] = None
    smtp_username: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_security: Optional[str] = None
    imap_username: Optional[str] = None
    enabled: bool
    daily_limit: int
    sent_today: Optional[int] = 0
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
