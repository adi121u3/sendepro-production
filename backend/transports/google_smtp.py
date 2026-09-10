"""Gmail SMTP submission authenticated with OAuth2 XOAUTH2."""
import base64
import smtplib
import ssl
from typing import Optional
from backend.transports.base import DeliveryResult
from backend.transports.mime_builder import build_outbound_message, message_as_bytes

class GmailSmtpOAuthTransport:
    def __init__(self, access_token: str, from_email: str, from_name: str = ""):
        self.access_token, self.from_email, self.from_name = access_token, from_email, from_name

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str = "", reply_to: Optional[str] = None, high_priority: bool = False, **_):
        message = build_outbound_message(from_email=self.from_email, from_name=self.from_name, to_email=to_email, subject=subject, html_body=html_body, text_body=text_body, reply_to=reply_to, high_priority=high_priority)
        auth = base64.b64encode(f"user={self.from_email}\x01auth=Bearer {self.access_token}\x01\x01".encode()).decode()
        server = None
        submission_started = False
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
            server.ehlo(); server.starttls(context=ssl.create_default_context()); server.ehlo()
            code, response = server.docmd("AUTH", "XOAUTH2 " + auth)
            if code != 235: raise smtplib.SMTPAuthenticationError(code, response)
            submission_started = True
            server.sendmail(self.from_email, [to_email], message_as_bytes(message))
            return DeliveryResult(status="SENT", message="Email accepted by Gmail SMTP using OAuth2.")
        except Exception as exc:
            return DeliveryResult(status="FAILED", message=f"Gmail SMTP OAuth failed: {exc}", retryable=not submission_started)
        finally:
            if server:
                try: server.quit()
                except Exception: server.close()
