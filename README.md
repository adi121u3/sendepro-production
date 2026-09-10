# Email Sender Pro

Email Sender Pro is a single-admin React and FastAPI application for sender accounts, leads, templates, drafts, campaigns, and delivery activity. It supports generic SMTP, Bell/Sympatico, ZeptoMail, Google browser OAuth with Gmail API, and Microsoft browser OAuth with SMTP XOAUTH2.

The Rackspace Email / EmailSRV preset uses `secure.emailsrvr.com`, port 465, and SSL/TLS with the full mailbox address as the username.

## Incoming mail (IMAP)

SMTP accounts can also store an IMAP host, port, security mode, and username. Incoming Mail uses a responsive three-pane mailbox, performs one batched header fetch for speed, loads full message bodies only when selected, and supports search, select-all, bulk mark-read, mark-unread, delete, reply, and refresh. Replies open the composer using the message's real `Reply-To` address. The correspondent must exist in Leads with a sender name because outbound sender names are lead-controlled.

ZeptoMail API is send-only and has no IMAP mailbox. To receive replies sent through ZeptoMail, set the campaign Reply-To to a real mailbox and configure that mailbox as a separate IMAP-enabled account. Campaign Reply-To is passed to ZeptoMail's API payload and to SMTP, Gmail, and Microsoft outbound messages.

## Requirements and setup

- Python 3.11+
- Node.js 20+

1. Copy `.env.example` to `.env`.
2. Replace every security placeholder. Use different random 32+ character values for `SECRET_KEY` and `CREDENTIAL_SECRET_KEY`.
3. Create a Python virtual environment and install `requirements.txt`.
4. Run `npm ci`.
5. Start the backend with `uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
6. Start the frontend with `npm run dev`.
7. Open `http://localhost:3001` and use the admin credentials configured in `.env`.

The SQLite database is created on first startup. Back it up with `python scripts/database_backup.py backup` while the app is idle.

## Google browser sign-in

Create a Google Cloud OAuth 2.0 Web application, enable Gmail API, and add the exact `OAUTH_REDIRECT_URI` (`http://localhost:3001/auth/google/callback`) as an authorized redirect URI. Configure the client ID and secret, restart the backend, sign in, and select **Connect Google OAuth**. The app requests identity, offline access, and Google's full mail scope because Google requires `https://mail.google.com/` for IMAP XOAUTH2. Public distribution may require Google verification.

Google sending uses Gmail's HTTPS API first for network reliability and can fall back to Gmail SMTP XOAUTH2. Incoming Gmail uses IMAP XOAUTH2 at `imap.gmail.com:993`.

## Microsoft browser sign-in

Create a Microsoft Entra ID application with a Web redirect URI exactly matching `MICROSOFT_REDIRECT_URI` (`http://localhost:3001/auth/microsoft/callback`). Add delegated `SMTP.Send` and `IMAP.AccessAsUser.All`, allow the required account types, create a client secret, and configure `.env`. Tenant `common` permits organizational and personal accounts; use a tenant ID to restrict it. The mailbox or tenant must allow authenticated SMTP and IMAP.

Accounts connected before SMTP/IMAP OAuth was added must be reconnected once so the provider can grant the new incoming-mail scope.

## Production build

Run `npm run build`. Serve `dist/` behind TLS and proxy `/api` to FastAPI. Set `CORS_ORIGINS` and OAuth redirects to the exact HTTPS production addresses. Never commit `.env`, databases, logs, backups, or credentials.

## Windows standalone application

From PowerShell on Windows, run `powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1`. The build creates `release\SendePro.exe` and copies your local `.env` beside it. Keep both files together and private. The standalone application hosts its UI and API only on `127.0.0.1:3001`, opens a native WebView2 window, stores `email_sender_pro.db` beside the executable, and supports the configured Google and Microsoft localhost OAuth callbacks. Microsoft Edge WebView2 Runtime is required (included with current Windows 10/11 installations).

## VPN, ISP, and provider restrictions

No desktop application can override a VPN, ISP firewall, or email-provider policy. The app provides actionable timeout diagnostics and supports HTTPS-based Gmail, Microsoft OAuth, and ZeptoMail API routes. If SMTP ports are blocked, use one of those authorized provider/API routes over HTTPS rather than attempting to bypass the block. Bell remains configured for its documented `smtphm.sympatico.ca` server with port 587 preferred and port 25 as its provider fallback; availability still depends on Bell and the current network.

## Security notes

- Administrative data APIs require a signed bearer token.
- OAuth begins from an authenticated session and callbacks require signed, expiring state.
- SMTP passwords, API keys, and OAuth tokens are encrypted before database storage.
- Keep `CREDENTIAL_SECRET_KEY` safe. Changing it makes stored credentials unreadable until accounts are reconnected.
- Review [PRODUCTION_AUDIT.md](PRODUCTION_AUDIT.md) before public or high-volume deployment.

## Delivery logs and sender names

Delivery Logs are database-backed records from real send attempts. They can be refreshed, individually selected and deleted, or cleared in full. Campaigns use the Sender Name on each matching Lead. Direct messages keep an editable From Name in the compose window, allowing a per-message override; if left blank, the Lead sender name is used. Email-like display names are rejected.

Outbound multipart messages use UTF-8 `text/plain` and `text/html` parts with `Content-Transfer-Encoding: quoted-printable`. SendePro does not add `User-Agent`, `X-Mailer`, `X-Classification-ID`, or `Content-Length` headers. A standards-compliant Message-ID uses the sender's domain. Providers and receiving servers can still add their own transport or classification headers after submission.

Provider acceptance is not proof of inbox placement. Before sending production mail, configure SPF, DKIM, and DMARC for the sender domain, warm new mailboxes gradually, send only to opted-in recipients, keep complaint/bounce rates low, and provide a working unsubscribe path for marketing mail. The application cannot override Gmail or Microsoft spam filtering.

The composer uses an immediate client-side send lock to prevent double-click submissions. Campaign retries honor each transport's retry safety. Bell disconnects during message submission are treated as an unknown result and are not retried automatically, because the server may already have accepted the message.

## Validation

Run `pytest -q` for backend tests and `npm run build` for frontend validation. Test real provider connections from Accounts with your own credentials.
