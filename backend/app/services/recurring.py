"""Recurring plans. Visits are generated a few weeks ahead so slots are held for the preferred professional."""
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.models.bookings import Booking, Subscription
from app.models.identity import Address, User
from app.services import availability as avail
from app.services import payment_events
from app.services.bookings import create_booking
from app.services.config_store import get_setting
from app.services.notify import notify
from app.services.payments import get_provider
from app.services.pricing import build_quote



def charge_saved_method(db: Session, b: Booking, method: str) -> None:
    """Off-session charge for generated visits. Sandbox settles synchronously; Stripe reports by webhook."""
    from app.services.finance import booking_payment

    pay = booking_payment(db, b.id)
    prov = get_provider()
    if pay is None or pay.status == "succeeded" or prov.name != "sandbox":
        return
    event = prov.confirm(pay.external_id, method, pay.amount_pence)
    payment_events.process_event(db, event, prov.name)


def generate_visits(db: Session, sub: Subscription, today: date | None = None) -> dict:
    if sub.status != "active":
        return {"created": 0, "skipped": 0}
    today = today or utcnow().date()
    step = 7 if sub.frequency == "weekly" else 14
    customer = db.get(User, sub.customer_id)
    addr = db.get(Address, sub.address_id)
    created = skipped = 0
    d = sub.next_visit_on
    horizon = today + timedelta(days=int(get_setting(db, "plan_horizon_days")))
    while d <= horizon:
        if d.isoformat() in (sub.skipped_dates or []):
            d += timedelta(days=step)
            continue
        start = datetime.combine(d, sub.start_time, tzinfo=avail.LONDON).astimezone(avail.ZoneInfo("UTC"))
        key = f"sub:{sub.id}:{d.isoformat()}"
        exists = db.scalar(select(Booking.id).where(Booking.customer_id == sub.customer_id, Booking.idempotency_key == key))
        if exists is None:
            try:
                with db.begin_nested():
                    quote = _quote_for(db, sub, customer, addr)
                    b = create_booking(
                        db, customer=customer, quotation=quote, address=addr, starts_at=start, provider_id=None, notes=None,
                        use_credit=False, idempotency_key=key, subscription_id=sub.id, saved_method=sub.payment_method_ref,
                        prefer_provider_id=sub.preferred_provider_id,
                    )
                    if sub.payment_method_ref:
                        charge_saved_method(db, b, sub.payment_method_ref)
                created += 1
            except AppError as exc:
                skipped += 1
                notify(db, customer, "plan_visit_unscheduled", "We could not schedule one of your visits",
                       f"We could not schedule your visit on {d.strftime('%A %-d %B')}: {exc.message}")
        d += timedelta(days=step)
    sub.next_visit_on = d
    return {"created": created, "skipped": skipped}


def _quote_for(db, sub, customer, addr):
    from app.models.catalogue import ServiceOffering

    o = db.get(ServiceOffering, sub.offering_id)
    base = build_quote(
        db, user=customer, offering_id=sub.offering_id, postcode=addr.postcode,
        minutes=(sub.duration_minutes - sum(a.extra_minutes for a in o.addons if a.code in sub.addon_codes)) if o.pricing_model == "hourly" else None,
        bedrooms=addr.bedrooms if o.pricing_model == "tiered" else None, addon_codes=sub.addon_codes, frequency=sub.frequency,
    )
    return base


def run_all(db: Session) -> dict:
    total = {"created": 0, "skipped": 0}
    for sub in db.scalars(select(Subscription).where(Subscription.status == "active")):
        r = generate_visits(db, sub)
        total["created"] += r["created"]
        total["skipped"] += r["skipped"]
    return total
