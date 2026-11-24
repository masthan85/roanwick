import logging
import smtplib
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.models.engagement import Notification
from app.models.identity import User

log = logging.getLogger("roanwick.notify")


def notify(db: Session, user: User | None, template: str, subject: str, body: str, channels: tuple[str, ...] = ("in_app", "email")) -> None:
    """Queue notifications. In-app entries are immediately visible; email and SMS go through the outbox."""
    get_settings()
    for ch in channels:
        if ch == "in_app" and user:
            db.add(Notification(user_id=user.id, channel="in_app", template=template, subject=subject, body=body, status="sent", sent_at=utcnow()))
        elif ch == "email" and user:
            db.add(Notification(user_id=user.id, channel="email", template=template, to_address=user.email, subject=subject, body=body))
        elif ch == "sms" and user and user.phone:
            db.add(Notification(user_id=user.id, channel="sms", template=template, to_address=user.phone, subject=subject, body=body))
    db.flush()


def dispatch_queued(db: Session, limit: int = 100) -> dict:
    """Send queued email and SMS. With the console providers the message is logged and marked sent."""
    get_settings()
    sent = failed = 0
    rows = db.scalars(select(Notification).where(Notification.status == "queued").order_by(Notification.created_at).limit(limit).with_for_update(skip_locked=True)).all()
    for n in rows:
        try:
            if n.channel == "email":
                _send_email(n)
            elif n.channel == "sms":
                _send_sms(n)
            n.status, n.sent_at = "sent", utcnow()
            sent += 1
        except Exception as exc:  # provider errors must not break the job
            n.status, n.error = "failed", str(exc)[:300]
            failed += 1
    return {"sent": sent, "failed": failed}


def _send_email(n: Notification) -> None:
    s = get_settings()
    if s.email_provider == "console":
        log.info("email_console to=%s subject=%s", n.to_address, n.subject)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.email_from, n.to_address, n.subject
    msg.set_content(n.body)
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


def _send_sms(n: Notification) -> None:
    s = get_settings()
    if s.sms_provider == "console":
        log.info("sms_console to=%s", n.to_address)
        return
    r = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages.json",
        data={"To": n.to_address, "From": s.twilio_from, "Body": n.body[:320]},
        auth=(s.twilio_account_sid, s.twilio_auth_token),
        timeout=15,
    )
    r.raise_for_status()
