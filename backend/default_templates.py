"""Install the optional built-in outreach templates exactly once per database."""

import logging

from backend.database import SessionLocal
from backend.models import Setting, Template

logger = logging.getLogger("email_sender_pro.default_templates")

_INSTALL_MARKER = "builtin_templates_v1_installed"

DEFAULT_TEMPLATES = (
    {
        "name": "Initial Introduction",
        "subject": "A quick introduction for {{Company}}",
        "body_html": """<p>Hello {{FirstName}},</p>
<p>I wanted to introduce myself and reach out regarding {{Company}}.</p>
<p>I would welcome a brief conversation to learn more about your current priorities and see whether there may be an opportunity to help.</p>
<p>Would you be available for a short conversation?</p>
<p>Best,<br>{{SenderName}}</p>""",
    },
    {
        "name": "Follow-Up",
        "subject": "Following up — {{Company}}",
        "body_html": """<p>Hello {{FirstName}},</p>
<p>I wanted to follow up on my previous message in case it was missed.</p>
<p>I would still appreciate the opportunity to learn more about {{Company}} and discuss whether we may be able to help with your current goals.</p>
<p>If someone else is the right person to contact, I would appreciate being pointed in the right direction.</p>
<p>Best,<br>{{SenderName}}</p>""",
    },
    {
        "name": "Final Follow-Up",
        "subject": "Closing the loop — {{Company}}",
        "body_html": """<p>Hello {{FirstName}},</p>
<p>I know schedules get busy, so I wanted to send one final follow-up.</p>
<p>If this is not a priority right now, no response is necessary. If the timing changes, I would be happy to reconnect.</p>
<p>Thank you for your time.</p>
<p>Best,<br>{{SenderName}}</p>""",
    },
)


def install_default_templates_once() -> None:
    """Add missing built-ins once without overwriting user content or recreating deletions."""
    db = SessionLocal()
    try:
        if db.query(Setting).filter(Setting.key == _INSTALL_MARKER).first():
            return

        existing_names = {row[0] for row in db.query(Template.name).all()}
        added = 0
        for template_data in DEFAULT_TEMPLATES:
            if template_data["name"] not in existing_names:
                db.add(Template(**template_data))
                added += 1

        db.add(Setting(key=_INSTALL_MARKER, value="1"))
        db.commit()
        logger.info("Installed %d built-in email template(s).", added)
    except Exception:
        db.rollback()
        logger.exception("Could not install built-in email templates.")
        raise
    finally:
        db.close()
