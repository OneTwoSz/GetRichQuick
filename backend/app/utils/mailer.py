"""
Outgoing email (password resets). Free options: Gmail / Google Workspace
with an app password, or any SMTP server. With SMTP unset the message is
written to the server log, so resets still work for whoever runs the
server (e.g. during a pilot) without exposing links anywhere public.
"""
import logging
import smtplib
from email.message import EmailMessage

from ..config import settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True if handed to an SMTP server."""
    if not smtp_configured():
        logger.warning("SMTP not configured — email to %s not sent. Subject: %s\n%s", to, subject, body)
        return False
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT or 587, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("sending email to %s failed: %s", to, exc)
        return False
