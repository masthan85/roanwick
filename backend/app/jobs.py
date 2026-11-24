"""Scheduled maintenance. Run every five minutes in production: python -m app.jobs"""
import logging
from datetime import date, timedelta

from sqlalchemy import select

from app.core.db import SessionLocal, utcnow
from app.models.providers import ProviderDocument
from app.services import bookings as svc
from app.services import finance, recurring
from app.services.config_store import get_setting
from app.services.notify import dispatch_queued, notify
from app.models.identity import User

log = logging.getLogger("roanwick.jobs")


def document_reminders(db) -> int:
    horizon = date.today() + timedelta(days=int(get_setting(db, "document_expiry_reminder_days")))
    sent = 0
    for d in db.scalars(select(ProviderDocument).where(ProviderDocument.status == "approved", ProviderDocument.expires_on.is_not(None), ProviderDocument.expires_on <= horizon)):
        if d.reminder_sent_for == d.expires_on:
            continue
        expired = d.expires_on < date.today()
        notify(db, db.get(User, d.provider_id), "document_expiry",
               f"Your {d.title} {'has expired' if expired else 'expires soon'}",
               f"{'It expired' if expired else 'It expires'} on {d.expires_on.strftime('%-d %B %Y')}. "
               + ("You will not receive new bookings until a valid replacement is approved." if expired else "Upload a replacement to keep receiving bookings."),
               ("in_app", "email"))
        d.reminder_sent_for = d.expires_on
        sent += 1
    return sent


def acceptance_timeouts(db) -> int:
    """Offered jobs nobody accepted in time are re-matched."""
    cutoff = utcnow() - timedelta(hours=int(get_setting(db, "provider_acceptance_hours")))
    from app.models.bookings import Booking

    n = 0
    for b in db.scalars(select(Booking).where(Booking.status == "awaiting_provider", Booking.provider_id.is_not(None), Booking.updated_at < cutoff).with_for_update(skip_locked=True)):
        prov = db.get(User, b.provider_id)
        svc.provider_decline(db, b, prov, "No response in time", request_note="no response")
        n += 1
    return n


def retention(db) -> dict:
    """Delete data that has outlived its purpose. Financial and booking records are never touched here."""
    from sqlalchemy import delete

    from app.models.engagement import Notification
    from app.models.identity import User
    from app.models.providers import ProviderProfile
    from app.models.system import IdempotencyRecord

    now = utcnow()
    idem = db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.created_at < now - timedelta(days=7))).rowcount
    notes = db.execute(delete(Notification).where(Notification.created_at < now - timedelta(days=180), Notification.status != "queued")).rowcount
    # Belt and braces: documents of anonymised professionals that survived an interrupted erasure.
    from app.api.auth import erase_provider_data

    docs = 0
    for uid in db.scalars(select(ProviderProfile.user_id).join(User, User.id == ProviderProfile.user_id).where(User.anonymised_at.is_not(None))):
        docs += erase_provider_data(db, uid)
    return {"idempotency_records": idem, "notifications": notes, "documents": docs}


def run_all(db) -> dict:
    result = {
        "holds_expired": svc.expire_holds(db),
        "acceptance_timeouts": acceptance_timeouts(db),
        "recurring": recurring.run_all(db),
        "payouts": finance.release_due_payouts(db),
        "document_reminders": document_reminders(db),
        "retention": retention(db),
    }
    result["notifications"] = dispatch_queued(db)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as s:
        out = run_all(s)
        s.commit()
        log.info("jobs_complete %s", out)
        print(out)
