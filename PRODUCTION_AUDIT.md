# Production audit

## Corrected in this release

- Removed bundled databases, backups, caches, virtual environment, stale builds, and obsolete duplicate source.
- Removed sample/seed account, lead, template, and campaign data.
- Removed the dormant tracking-pixel endpoint and all campaign pixel injection.
- HTML-only incoming messages render inside a sandboxed, network-blocked preview frame with normalized readable typography.
- Fixed campaign editing so Save updates the existing campaign instead of creating a duplicate.
- Added a Windows PyInstaller + WebView2 standalone build workflow.
- Disabled post-submission SMTP retries when delivery status is uncertain to reduce duplicate delivery risk.
- Removed hard-coded admin credentials and predictable signing-key fallback.
- Replaced manual OAuth token entry with authenticated Google and Microsoft browser OAuth.
- Added signed, expiring OAuth state, server-side code exchange, encrypted tokens, security headers, and configurable CORS.
- Fixed the frontend OAuth route mismatch, missing multipart dependency, mutable schema defaults, stale documentation, and large vendor bundle.
- Connected the Delivery Logs screen directly to persisted `delivery_logs` records rather than generic audit events.
- Added the same persisted recipient-level records directly beneath each campaign, with recipient, sender name, provider/account, timestamp, provider message ID, and failure details.
- Renamed the successful SMTP result to **Provider accepted** because an SMTP/API acknowledgement is not proof of inbox delivery.
- Recorded the exact effective sender name on successful and failed delivery attempts.
- Campaigns use Lead-owned sender names; direct compose messages allow an explicit editable From Name override.
- Added SMTP password show/hide controls and actionable Windows 10060/TLS diagnostics.
- Added a Rackspace Email / EmailSRV preset for `secure.emailsrvr.com:465` with SSL/TLS.
- Added real IMAP incoming mail with batched header fetching, sandboxed HTML/text preview, reply routing, and bulk read/unread/delete.
- Removed misleading CC/BCC and typed-filename attachment controls that were not connected to outbound transports.
- Corrected composer formatting actions to insert valid HTML rather than visible bracket placeholders.
- Verified Reply-To propagation for ZeptoMail API, SMTP, Gmail, Microsoft, and campaign processing.
- Added Google and Microsoft IMAP XOAUTH2 using encrypted access/refresh tokens and automatic token refresh.
- Standardized local OAuth callbacks on the frontend proxy: Google uses `OAUTH_REDIRECT_URI=http://localhost:3001/auth/google/callback`; Microsoft uses `MICROSOFT_REDIRECT_URI=http://localhost:3001/auth/microsoft/callback`.

## Pros

- Clear React/FastAPI separation and compact SQLite model.
- SMTP, Bell/Sympatico, ZeptoMail, Gmail API, and Microsoft OAuth SMTP delivery.
- Encrypted credentials, pacing, retry handling, sender rotation, templates, imports, drafts, and activity logs.
- Authenticated administrative routes and straightforward local deployment.

## Cons and operating limits

- SQLite and in-process workers suit one local instance, not multiple servers or high-volume concurrency.
- Workers do not survive a process restart; distributed use needs a durable job queue.
- Lightweight SQLite migrations are used instead of versioned Alembic migrations.
- Login throttling and multi-user roles are not included; use a trusted network or rate-limiting reverse proxy.
- OAuth requires provider-created client credentials and exact redirect URIs.
- Deliverability depends on provider limits, SPF, DKIM, DMARC, consent, unsubscribe handling, and legal compliance.
- Tests do not send live mail or exercise real provider accounts.
- The standalone build must be compiled on Windows; the produced executable was not cross-compiled in this Linux workspace.
- File attachments and CC/BCC sending are intentionally not exposed until all provider transports implement them consistently.

## Recommended hosted/SaaS stage

Use PostgreSQL, Alembic, a durable queue, provider webhooks, centralized logs, automated backups, TLS, login rate limiting, audit retention, and per-user authorization.
