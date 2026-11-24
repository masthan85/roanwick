"""Single entry point for payment events, used by the webhook endpoint and by the sandbox.
Events are recorded first, so a duplicate delivery is acknowledged without being re-applied
and a failed one can be retried by the provider."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models.bookings import Booking
from app.models.finance import Payment
from app.models.system import WebhookEvent
from app.services import bookings as booking_svc

log = logging.getLogger("roanwick.payments")


class EventError(Exception):
    pass


def process_event(db: Session, event: dict, provider_name: str) -> str:
    """Returns 'processed', 'duplicate' or 'ignored'. Raises EventError (state rolled back to the savepoint)."""
    ev = db.get(WebhookEvent, event["id"])
    if ev is not None and ev.status == "processed":
        return "duplicate"
    if ev is None:
        ev = WebhookEvent(event_id=event["id"], provider=provider_name, event_type=event["type"], payload=event)
        db.add(ev)
    ev.attempts = (ev.attempts or 0) + 1
    db.flush()
    try:
        with db.begin_nested():
            outcome = _apply(db, event)
    except Exception as exc:
        ev.status, ev.error = "failed", str(exc)[:300]
        db.flush()
        log.warning("payment_event_failed id=%s type=%s error=%s", event["id"], event["type"], exc)
        raise EventError(str(exc)) from exc
    ev.status, ev.processed_at, ev.error = "processed", utcnow(), None
    db.flush()
    return outcome


def _apply(db: Session, event: dict) -> str:
    t, d = event["type"], event.get("data", {})
    if t in ("payment_intent.succeeded", "payment_intent.payment_failed"):
        pay = db.scalar(select(Payment).where(Payment.external_id == d.get("external_id")).with_for_update())
        if pay is None:
            raise EventError(f"Unknown payment {d.get('external_id')}")
        b = db.scalar(select(Booking).where(Booking.id == pay.booking_id).with_for_update())
        if t == "payment_intent.succeeded":
            if d.get("amount") is not None and d["amount"] != pay.amount_pence:
                raise EventError(f"Amount mismatch: expected {pay.amount_pence}, received {d['amount']}")
            booking_svc.on_payment_succeeded(db, b, pay, fee=d.get("fee"), fee_actual=d.get("fee") is not None)
        else:
            booking_svc.on_payment_failed(db, pay, d.get("message", "Payment failed."))
        return "processed"
    if t == "charge.refunded":
        # Refunds are recorded when we issue them. This event only confirms them, so there is nothing to apply.
        return "processed"
    return "ignored"
