"""Booking lifecycle: creation with matching, payment events, cancellation, rescheduling, completion."""
import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import Conflict, Forbidden, NotFound, Unprocessable
from app.models.bookings import Booking, BookingLine, BookingStatusHistory
from app.models.catalogue import Quotation, ServiceOffering
from app.models.engagement import CreditTransaction, Promotion, PromotionRedemption
from app.models.finance import Payment
from app.models.identity import Address, CustomerProfile, User
from app.models.providers import ProviderProfile
from app.services import availability as avail
from app.services import finance, quality
from app.services.config_store import flag, get_setting
from app.services.notify import notify
from app.services.payments import get_provider
from app.services.pricing import refund_bps_for

ALLOWED = {
    "pending_payment": {"awaiting_provider", "confirmed", "expired", "cancelled"},
    "awaiting_provider": {"confirmed", "cancelled"},
    "confirmed": {"in_progress", "cancelled", "completed"},
    "in_progress": {"completed", "cancelled"},
}
TERMINAL = {"completed", "cancelled", "expired"}
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_reference() -> str:
    return "RW-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


def transition(db: Session, b: Booking, to: str, actor: User | None = None, note: str | None = None) -> None:
    if to not in ALLOWED.get(b.status, set()):
        raise Conflict(f"A booking that is {b.status.replace('_', ' ')} cannot become {to.replace('_', ' ')}.", code="invalid_transition")
    b.history.append(BookingStatusHistory(from_status=b.status, to_status=to, actor_user_id=actor.id if actor else None, note=note))
    b.status = to


def _is_exclusion_violation(exc: IntegrityError) -> bool:
    return getattr(exc.orig, "sqlstate", None) == "23P01"


def expire_holds(db: Session) -> int:
    now = utcnow()
    rows = db.scalars(select(Booking).where(Booking.status == "pending_payment", Booking.hold_expires_at < now).with_for_update(skip_locked=True)).all()
    for b in rows:
        transition(b, "expired", note="Payment was not completed in time.") if False else None
        b.history.append(BookingStatusHistory(from_status=b.status, to_status="expired", note="Payment was not completed in time."))
        b.status = "expired"
        _restore_credit(db, b)
        for p in db.scalars(select(Payment).where(Payment.booking_id == b.id, Payment.status.in_(("requires_payment", "failed")))):
            p.status = "cancelled"
    if rows:
        db.flush()
    return len(rows)


def _restore_credit(db: Session, b: Booking) -> None:
    spent = db.scalar(select(CreditTransaction).where(CreditTransaction.booking_id == b.id, CreditTransaction.reason == "booking_spend"))
    refunded = db.scalar(select(CreditTransaction).where(CreditTransaction.booking_id == b.id, CreditTransaction.reason == "booking_refund"))
    if spent and not refunded:
        db.add(CreditTransaction(user_id=b.customer_id, amount_pence=-spent.amount_pence, reason="booking_refund", booking_id=b.id))
        db.get(CustomerProfile, b.customer_id).credit_pence += -spent.amount_pence


def create_booking(
    db: Session, *, customer: User, quotation: Quotation, address: Address, starts_at: datetime, provider_id: uuid.UUID | None,
    notes: str | None, use_credit: bool, idempotency_key: str | None, subscription_id: uuid.UUID | None = None,
    saved_method: str | None = None, ignore_notice: bool = False, prefer_provider_id: uuid.UUID | None = None,
) -> Booking:
    expire_holds(db)
    now = utcnow()
    if quotation.user_id not in (None, customer.id):
        raise NotFound("Quotation not found.")
    if quotation.expires_at < now and not ignore_notice:
        raise Unprocessable("This quotation has expired. Please get a fresh price.", code="quote_expired")
    if address.user_id != customer.id:
        raise NotFound("Address not found.")
    if address.outward_code != quotation.outward_code:
        raise Unprocessable("The address does not match the postcode that was priced.", code="address_mismatch")
    if starts_at.minute % avail.GRID_MINUTES or starts_at.second:
        raise Unprocessable("Start times must be on the hour or half hour.", code="bad_start_time")
    if not ignore_notice:
        if starts_at < now + timedelta(hours=int(get_setting(db, "min_notice_hours"))):
            raise Unprocessable(f"We need at least {get_setting(db, 'min_notice_hours')} hours' notice.", code="too_soon")
        if starts_at > now + timedelta(days=int(get_setting(db, "booking_horizon_days"))):
            raise Unprocessable("That date is too far ahead.", code="too_far")
    if provider_id and not flag(db, "customer_chooses_provider"):
        raise Unprocessable("Choosing a professional is not currently available.")

    offering = db.get(ServiceOffering, quotation.offering_id)
    ends_at = starts_at + timedelta(minutes=quotation.duration_minutes)
    blocked_until = ends_at + timedelta(minutes=offering.buffer_minutes)
    prefer = [provider_id] if provider_id else ([prefer_provider_id] if prefer_provider_id else [])
    cands = avail.rank_candidates(db, offering, quotation.outward_code, starts_at, quotation.duration_minutes, prefer=prefer, customer_id=customer.id)
    if provider_id:
        cands = [p for p in cands if p.user_id == provider_id]
        if not cands:
            raise Conflict("That professional is not available at this time.", code="provider_unavailable")
    if not cands:
        raise Conflict("No professional is available at that time. Please choose another slot.", code="no_availability")

    credit = 0
    if use_credit:
        credit = min(db.get(CustomerProfile, customer.id).credit_pence, quotation.total_pence)
    booking = None
    for cand in cands:
        b = Booking(
            reference=new_reference(), customer_id=customer.id, provider_id=cand.user_id, offering_id=offering.id,
            quotation_id=quotation.id, subscription_id=subscription_id, status="pending_payment", starts_at=starts_at,
            ends_at=ends_at, blocked_until=blocked_until, assignment_mode="chosen" if provider_id else "auto",
            address_snapshot={
                "line1": address.line1, "line2": address.line2, "city": address.city, "postcode": address.postcode,
                "access_notes": address.access_notes, "bedrooms": address.bedrooms,
            },
            outward_code=address.outward_code, inputs=quotation.inputs, customer_notes=notes, total_pence=quotation.total_pence,
            hold_expires_at=now + timedelta(minutes=int(get_setting(db, "hold_minutes"))), idempotency_key=idempotency_key,
            terms_snapshot=quotation.terms,
        )
        for l in quotation.lines:
            b.lines.append(BookingLine(position=l.position, kind=l.kind, description=l.description, amount_pence=l.amount_pence))
        b.history.append(BookingStatusHistory(from_status=None, to_status="pending_payment", actor_user_id=customer.id, note="Booking created"))
        try:
            with db.begin_nested():  # savepoint: a lost race on one professional must not poison the transaction
                db.add(b)
                db.flush()
            booking = b
            break
        except IntegrityError as exc:
            if _is_exclusion_violation(exc):
                continue
            if "uq_booking_customer_idem" in str(exc.orig):
                raise Conflict("This booking request was already submitted.", code="duplicate_request")
            raise
    if booking is None:
        raise Conflict("That time was just taken. Please choose another slot.", code="slot_taken")

    if credit:
        db.add(CreditTransaction(user_id=customer.id, amount_pence=-credit, reason="booking_spend", booking_id=booking.id))
        db.get(CustomerProfile, customer.id).credit_pence -= credit
    cash = booking.total_pence - credit
    prov = get_provider()
    if cash > 0:
        intent = prov.create_intent(cash, booking_ref=booking.reference, customer_email=customer.email, idempotency_key=f"booking:{booking.id}", saved_method=saved_method)
        pay = Payment(
            booking_id=booking.id, customer_id=customer.id, provider_name=prov.name, external_id=intent.external_id, amount_pence=cash,
            credit_applied_pence=credit, status="requires_payment", client_secret=intent.client_secret, idempotency_key=f"booking:{booking.id}",
        )
        db.add(pay)
        db.flush()
    else:
        pay = Payment(
            booking_id=booking.id, customer_id=customer.id, provider_name="credit", external_id=f"credit_{booking.id.hex}", amount_pence=0,
            credit_applied_pence=credit, status="requires_payment", idempotency_key=f"booking:{booking.id}",
        )
        db.add(pay)
        db.flush()
        on_payment_succeeded(db, booking, pay, fee=0, fee_actual=True)
    return booking


def on_payment_succeeded(db: Session, b: Booking, pay: Payment, fee: int | None, fee_actual: bool) -> None:
    if pay.status == "succeeded":
        return
    pay.status, pay.paid_at, pay.failure_message = "succeeded", utcnow(), None
    if fee is not None:
        pay.processing_fee_pence, pay.processing_fee_source = fee, "actual" if fee_actual else "estimated"
    if b.status != "pending_payment":
        # Payment arrived after the hold lapsed or the booking was cancelled: refund rather than silently keep the money.
        finance.issue_refund(db, b, pay.amount_pence + pay.credit_applied_pence if pay.amount_pence else pay.credit_applied_pence, reason="other", funded_by="platform", key=f"late:{pay.id}")
        notify(db, db.get(User, b.customer_id), "payment_refunded_late", "Payment refunded",
               f"Your payment for {b.reference} arrived after the time slot was released, so it has been refunded in full.")
        return
    q = db.get(Quotation, b.quotation_id) if b.quotation_id else None
    if q and q.promo_code:
        promo = db.scalar(select(Promotion).where(Promotion.code == q.promo_code))
        disc = -sum(l.amount_pence for l in b.lines if l.kind == "promo")
        if promo and disc:
            db.add(PromotionRedemption(promotion_id=promo.id, user_id=b.customer_id, booking_id=b.id, discount_pence=disc))
            promo.redemption_count += 1
    provider = db.get(ProviderProfile, b.provider_id)
    customer = db.get(User, b.customer_id)
    when = avail.local(b.starts_at).strftime("%A %-d %B at %H:%M")
    if provider.auto_accept:
        transition(db, b, "confirmed", note="Payment received. Confirmed automatically within the professional's published availability.")
        notify(db, customer, "booking_confirmed", f"Booking {b.reference} confirmed", f"Your booking with {provider.display_name} is confirmed for {when}.", ("in_app", "email", "sms"))
    else:
        transition(db, b, "awaiting_provider", note="Payment received. Waiting for the professional to accept.")
        notify(db, customer, "booking_requested", f"Booking {b.reference} requested", f"Thank you. {provider.display_name} has until the acceptance deadline to confirm your booking for {when}. You will not be charged twice if it is re-assigned.")
    notify(db, db.get(User, b.provider_id), "new_job", f"New job {b.reference}", f"{when} in {b.outward_code}. Open the app to {'view' if provider.auto_accept else 'accept or decline'} the job.", ("in_app", "email", "sms"))


def on_payment_failed(db: Session, pay: Payment, message: str) -> None:
    if pay.status == "succeeded":
        return
    pay.status, pay.failure_message = "failed", message


def _rematch(db: Session, b: Booking, exclude: list[uuid.UUID]) -> bool:
    offering = db.get(ServiceOffering, b.offering_id)
    cands = avail.rank_candidates(db, offering, b.outward_code, b.starts_at, int((b.ends_at - b.starts_at).total_seconds() // 60), exclude=exclude, customer_id=b.customer_id)
    for cand in cands:
        try:
            with db.begin_nested():
                b.provider_id = cand.user_id
                db.flush()
        except IntegrityError as exc:
            if _is_exclusion_violation(exc):
                continue
            raise
        b.assignment_mode = "auto"
        return True
    return False


def provider_decline(db: Session, b: Booking, provider: User, reason: str | None, request_note: str = "declined") -> None:
    """Provider rejects an offered job, or withdraws from a confirmed one. We re-match; if nobody is free the
    booking is left unassigned for operations to resolve (or the customer to cancel with a full refund)."""
    if b.provider_id != provider.id:
        raise Forbidden("This is not your job.")
    if b.status not in ("awaiting_provider", "confirmed"):
        raise Conflict("This job can no longer be declined.", code="invalid_transition")
    prof = db.get(ProviderProfile, provider.id)
    was_confirmed = b.status == "confirmed"
    b.rejected_provider_ids = [*b.rejected_provider_ids, str(provider.id)]
    if was_confirmed:
        prof.cancel_count += 1
        db.flush()
        quality.evaluate(db, provider.id)
    b.provider_id = None
    db.flush()
    excl = [uuid.UUID(x) for x in b.rejected_provider_ids]
    if _rematch(db, b, excl):
        newp = db.get(ProviderProfile, b.provider_id)
        status_to = "confirmed" if newp.auto_accept else "awaiting_provider"
        if b.status != status_to:
            b.history.append(BookingStatusHistory(from_status=b.status, to_status=status_to, note=f"Re-assigned after {request_note}."))
            b.status = status_to
        notify(db, db.get(User, b.provider_id), "new_job", f"New job {b.reference}", "A job has been offered to you.", ("in_app", "email", "sms"))
        notify(db, db.get(User, b.customer_id), "booking_reassigned", f"Your professional has changed for {b.reference}",
               f"{prof.display_name} can no longer do this visit, so we have assigned {newp.display_name}. You can cancel for a full refund if you prefer.")
    else:
        if was_confirmed:
            b.history.append(BookingStatusHistory(from_status="confirmed", to_status="awaiting_provider", note="Provider withdrew; no replacement found yet."))
            b.status = "awaiting_provider"
        notify(db, db.get(User, b.customer_id), "booking_unassigned", f"We are finding a new professional for {b.reference}",
               "Your professional is no longer available and we have not yet found a replacement. Our team is on it. You can cancel for a full refund at any time.")


def provider_accept(db: Session, b: Booking, provider: User) -> None:
    if b.provider_id != provider.id:
        raise Forbidden("This is not your job.")
    transition(db, b, "confirmed", provider, "Accepted by professional")
    notify(db, db.get(User, b.customer_id), "booking_confirmed", f"Booking {b.reference} confirmed",
           f"{db.get(ProviderProfile, provider.id).display_name} has accepted your booking for {avail.local(b.starts_at).strftime('%A %-d %B at %H:%M')}.", ("in_app", "email", "sms"))


def refund_preview(db: Session, b: Booking, now: datetime | None = None) -> dict:
    now = now or utcnow()
    if b.status == "pending_payment":
        return {"refund_pence": 0, "retained_pence": 0, "refund_bps": 0, "note": "You have not been charged."}
    hours = (b.starts_at - now).total_seconds() / 3600
    bps = 10000 if b.provider_id is None else refund_bps_for(db, hours)
    refund = round(b.total_pence * bps / 10000)
    return {"refund_pence": refund, "retained_pence": b.total_pence - refund, "refund_bps": bps, "hours_before": round(hours, 1), "note": None}


def cancel_booking(db: Session, b: Booking, actor: User, by: str, reason: str | None) -> dict:
    if b.status in TERMINAL:
        raise Conflict("This booking is already closed.", code="invalid_transition")
    customer = db.get(User, b.customer_id)
    pay = finance.booking_payment(db, b.id)
    refund_amt = retained = 0
    if b.status == "pending_payment":
        transition(db, b, "cancelled", actor, reason)
        _restore_credit(db, b)
        if pay:
            pay.status = "cancelled"
    else:
        if by == "customer":
            prev = refund_preview(db, b)
            refund_amt, retained = prev["refund_pence"], prev["retained_pence"]
        else:
            refund_amt = b.total_pence
        if b.status == "in_progress" and by == "customer":
            raise Conflict("This visit has already started. Please contact support.", code="in_progress")
        transition(db, b, "cancelled", actor, reason)
        if pay and pay.status in ("succeeded", "partially_refunded"):
            finance.issue_refund(
                db, b, refund_amt, reason="cancellation" if by == "customer" else "provider_cancelled",
                funded_by="customer_policy" if by == "customer" else "platform", actor_id=actor.id, key=f"cancel:{b.id}",
            )
        if retained > 0 and b.provider_id:
            b.completed_at = utcnow()
            fin = finance.finalise_booking(db, b, "late_cancelled", retained_pence=retained)
            finance.create_payout(db, b, fin)
    b.cancelled_at, b.cancelled_by, b.cancel_reason = utcnow(), by, reason
    if by == "provider" and b.provider_id:
        db.get(ProviderProfile, b.provider_id).cancel_count += 1
    notify(db, customer, "booking_cancelled", f"Booking {b.reference} cancelled",
           f"Your booking has been cancelled. Refund: £{refund_amt / 100:.2f}." if refund_amt else "Your booking has been cancelled.", ("in_app", "email"))
    if b.provider_id and by != "provider":
        notify(db, db.get(User, b.provider_id), "booking_cancelled", f"Job {b.reference} cancelled", "The customer has cancelled this job.", ("in_app", "email"))
    return {"refund_pence": refund_amt, "retained_pence": retained}


def reschedule(db: Session, b: Booking, actor: User, new_start: datetime, allow_other_provider: bool) -> None:
    if b.status not in ("confirmed", "awaiting_provider"):
        raise Conflict("Only upcoming bookings can be rescheduled.", code="invalid_transition")
    now = utcnow()
    if refund_bps_for(db, (b.starts_at - now).total_seconds() / 3600) < 10000:
        raise Unprocessable("This visit is too close to its start time to move. The cancellation terms apply.", code="too_late_to_reschedule")
    if new_start < now + timedelta(hours=int(get_setting(db, "min_notice_hours"))) or new_start.minute % avail.GRID_MINUTES:
        raise Unprocessable("Please choose a later time on the hour or half hour.", code="bad_start_time")
    dur = b.ends_at - b.starts_at
    offering = db.get(ServiceOffering, b.offering_id)
    new_end, new_block = new_start + dur, new_start + dur + timedelta(minutes=offering.buffer_minutes)
    old = (b.starts_at, b.ends_at, b.blocked_until, b.provider_id)
    if b.provider_id and avail.provider_free(db, b.provider_id, new_start, new_end, offering.buffer_minutes, ignore_booking_id=b.id):
        try:
            with db.begin_nested():
                b.starts_at, b.ends_at, b.blocked_until = new_start, new_end, new_block
                db.flush()
        except IntegrityError as exc:
            if not _is_exclusion_violation(exc):
                raise
            raise Conflict("Your professional is not free at that time.", code="provider_unavailable")
    elif allow_other_provider:
        b.starts_at, b.ends_at, b.blocked_until, b.provider_id = new_start, new_end, new_block, None
        if not _rematch(db, b, []):
            b.starts_at, b.ends_at, b.blocked_until, b.provider_id = old
            raise Conflict("No professional is available at that time.", code="no_availability")
    else:
        raise Conflict("Your professional is not free at that time. You can allow another professional or choose a different time.", code="provider_unavailable")
    b.rescheduled_count += 1
    b.history.append(BookingStatusHistory(from_status=b.status, to_status=b.status, actor_user_id=actor.id, note=f"Rescheduled from {old[0].isoformat()}"))
    if b.provider_id:
        notify(db, db.get(User, b.provider_id), "job_rescheduled", f"Job {b.reference} moved", f"New time: {avail.local(new_start).strftime('%A %-d %B at %H:%M')}.", ("in_app", "email"))


def start_job(db: Session, b: Booking, provider: User) -> None:
    if b.provider_id != provider.id:
        raise Forbidden("This is not your job.")
    now = utcnow()
    if now < b.starts_at - timedelta(hours=1):
        raise Unprocessable("You can start a job up to an hour before its scheduled time.", code="too_early")
    transition(db, b, "in_progress", provider, "Started")
    b.started_at = now
    if now > b.starts_at + timedelta(minutes=15):
        b.arrived_late = True
        db.get(ProviderProfile, provider.id).late_count += 1


def complete_job(db: Session, b: Booking, provider: User) -> None:
    if b.provider_id != provider.id:
        raise Forbidden("This is not your job.")
    if b.status == "confirmed":
        start_job(db, b, provider)
    transition(db, b, "completed", provider, "Completed")
    b.completed_at = utcnow()
    prof = db.get(ProviderProfile, provider.id)
    prof.jobs_completed += 1
    first_completed = db.query(Booking).filter(Booking.customer_id == b.customer_id, Booking.status == "completed", Booking.id != b.id).count() == 0
    fin = finance.finalise_booking(db, b, "completed")
    finance.create_payout(db, b, fin)
    customer = db.get(User, b.customer_id)
    notify(db, customer, "review_prompt", f"How was your visit? ({b.reference})", f"{prof.display_name} has marked your visit as complete. Please leave a review.", ("in_app", "email"))
    if first_completed and flag(db, "referrals"):
        _referral_rewards(db, b)
    quality.evaluate(db, provider.id)


def _referral_rewards(db: Session, b: Booking) -> None:
    prof = db.get(CustomerProfile, b.customer_id)
    if not prof or not prof.referred_by_user_id:
        return
    reward, welcome = int(get_setting(db, "referral_reward_pence")), int(get_setting(db, "referral_welcome_pence"))
    for uid, amt, reason in ((prof.referred_by_user_id, reward, "referral_reward"), (b.customer_id, welcome, "referral_welcome")):
        if amt > 0:
            db.add(CreditTransaction(user_id=uid, amount_pence=amt, reason=reason, booking_id=b.id))
            db.get(CustomerProfile, uid).credit_pence += amt
            notify(db, db.get(User, uid), reason, "You have referral credit", f"£{amt / 100:.2f} of credit has been added to your account.")


def admin_assign(db: Session, b: Booking, provider_id: uuid.UUID, actor: User) -> None:
    if b.status not in ("awaiting_provider", "confirmed", "pending_payment"):
        raise Conflict("This booking cannot be re-assigned.", code="invalid_transition")
    prof = db.get(ProviderProfile, provider_id)
    offering = db.get(ServiceOffering, b.offering_id)
    from app.services.verification import is_bookable_for

    if prof is None or not is_bookable_for(db, prof, offering):
        raise Unprocessable("That professional is not approved and fully verified for this service.", code="provider_not_eligible")
    try:
        with db.begin_nested():
            b.provider_id = provider_id
            db.flush()
    except IntegrityError as exc:
        if _is_exclusion_violation(exc):
            raise Conflict("That professional already has a booking at this time.", code="provider_unavailable")
        raise
    b.assignment_mode = "admin"
    if b.status == "awaiting_provider" and prof.auto_accept:
        b.history.append(BookingStatusHistory(from_status="awaiting_provider", to_status="confirmed", actor_user_id=actor.id, note="Assigned by operations"))
        b.status = "confirmed"
    notify(db, db.get(User, provider_id), "new_job", f"New job {b.reference}", "Operations has assigned you a job.", ("in_app", "email", "sms"))
    notify(db, db.get(User, b.customer_id), "booking_assigned", f"A professional has been assigned to {b.reference}", f"{prof.display_name} will carry out your visit.")
