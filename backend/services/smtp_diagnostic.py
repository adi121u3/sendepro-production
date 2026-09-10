import smtplib
import socket
import ssl
import logging

logger = logging.getLogger(__name__)

def diagnose_smtp_error(e: Exception) -> str:
    """
    Maps smtplib exceptions (socket, timeout, auth) into clear, non-sensitive diagnostic messages for the UI.
    """
    err_str = str(e)
    lower = err_str.lower()
    if isinstance(e, smtplib.SMTPAuthenticationError):
        code, resp = e.smtp_code, e.smtp_error
        resp_msg = resp.decode('utf-8', errors='ignore') if isinstance(resp, bytes) else str(resp)
        return f"SMTP Authentication failed (Code {code}): Invalid username or password ({resp_msg})"
    elif isinstance(e, smtplib.SMTPConnectError):
        return f"SMTP Connection failed: Server refused connection or is unreachable."
    elif isinstance(e, socket.timeout) or isinstance(e, TimeoutError) or "10060" in lower or "timed out" in lower:
        return "SMTP connection timed out (Windows 10060). The server did not answer; this is normally the wrong host/port, a firewall or antivirus block, a VPN/ISP restriction, or SMTP being disabled by the provider—not a bad password. Verify the provider hostname, use STARTTLS/587 or SSL/465 as documented, disable VPN temporarily, and confirm outbound SMTP is allowed."
    elif isinstance(e, smtplib.SMTPServerDisconnected):
        return "SMTP server closed the connection. Verify the security mode matches the port: STARTTLS usually uses 587; SSL/TLS usually uses 465."
    elif isinstance(e, socket.gaierror):
        return f"DNS resolution failed: Could not resolve SMTP host."
    elif isinstance(e, ssl.SSLError):
        return f"TLS/SSL negotiation failed: {err_str}"
    elif isinstance(e, (ConnectionRefusedError, OSError)):
        return f"Network connection to the SMTP server failed: {err_str}. Verify host, port, firewall, VPN, and provider SMTP access."
    else:
        return f"SMTP error: {err_str}"
