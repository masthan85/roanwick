"""Per-booking economics, refunds and provider payouts.

Definitions used everywhere in reporting:
- Service value: labour, add-ons and plan discount. This is the commission basis.
- Platform revenue: commission + customer booking fee - platform-funded promotional discounts.
- Contribution: platform revenue - card processing fees - platform-funded refunds.
Gross booking value (cash taken from customers) is never treated as revenue.
"""
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError, Unprocessable
from app.models.bookings import Booking
from app.models.engagement import CreditTransaction
from app.models.finance import BookingFinancial, Payment, Payout, ProviderAdjustment, Refund
from app.models.identity import CustomerProfile, User
from app.models.providers import ProviderProfile
from app.services.config_store import get_setting
from app.services.notify import notify
from app.services.payments import get_provider


def estimate_processing_fee(db: Session, cash_pence: int) -> int:
    if cash_pence <= 0:
        return 0
    return round(cash_pence * int(get_setting(db, "processing_fee_bps")) / 10000) + int(get_setting(db, "processing_fee_fixed_pence"))


def booking_payment(db: Session, booking_id: uuid.UUID) -> Payment | None:
    return db.scalar(select(Payment).where(Payment.booking_id == booking_id).order_by(Payment.created_at.desc()))


def commission_bps_for(db: Session, provider: ProviderProfile | None) -> int:
    if provider is not None and provider.commission_override_bps is not None:
        return provider.commission_override_bps
    return int(get_setting(db, "commission_bps"))


def _line_sum(b: Booking, kinds: tuple[str, ...]) -> int:
    return sum(l.amount_pence for l in b.lines if l.kind in kinds)


def finalise_booking(db: Session, b: Booking, outcome: str, retained_pence: int | None = None) -> BookingFinancial:
    pay = booking_payment(db, b.id)
    provider = db.get(ProviderProfile, b.provider_id) if b.provider_id else None
    bps = commission_bps_for(db, provider)
    if outcome == "completed":
        service_value = _line_sum(b, ("labour", "addon", "discount"))
        fee = _line_sum(b, ("fee",))
        promo_cost = -_line_sum(b, ("promo", "bundle"))
    else:  # late-cancelled: retained cancellation charge is treated as service value, no fee or promo
        service_value, fee, promo_cost = retained_pence or 0, 0, 0
    commission = round(service_value * bps / 10000)
    cash = pay.amount_pence if pay and pay.status in ("succeeded", "refunded", "partially_refunded") else 0
    fin = db.get(BookingFinancial, b.id) or BookingFinancial(booking_id=b.id)
    refunds = db.scalars(select(Refund).where(Refund.booking_id == b.id, Refund.status != "failed")).all()
    fin.gross_paid_pence = cash
    fin.credit_used_pence = pay.credit_applied_pence if pay else 0
    fin.service_value_pence = service_value
    fin.fee_pence = fee
    fin.promo_cost_pence = promo_cost
    fin.commission_bps = bps
    fin.commission_pence = commission
    fin.provider_earning_pence = service_value - commission
    fin.processing_fee_pence = (pay.processing_fee_pence if pay and pay.processing_fee_pence is not None else estimate_processing_fee(db, cash))
    fin.processing_fee_source = pay.processing_fee_source if pay and pay.processing_fee_pence is not None else "estimated"
    fin.refunded_pence = sum(r.amount_pence for r in refunds)
    fin.platform_funded_refund_pence = sum(r.amount_pence for r in refunds if r.funded_by == "platform")
    fin.outcome = outcome
    fin.outward_code = b.outward_code
    fin.offering_id = b.offering_id
    fin.finalised_at = fin.finalised_at or utcnow()
    db.add(fin)
    db.flush()
    return fin


def create_payout(db: Session, b: Booking, fin: BookingFinancial) -> Payout | None:
    if not b.provider_id or fin.provider_earning_pence <= 0:
        return None
    existing = db.scalar(select(Payout).where(Payout.booking_id == b.id))
    if existing:
        return existing
    p = Payout(
        provider_id=b.provider_id, booking_id=b.id, gross_pence=fin.service_value_pence, commission_pence=fin.commission_pence,
        amount_pence=fin.provider_earning_pence, status="pending",
        release_at=(b.completed_at or utcnow()) + timedelta(days=int(get_setting(db, "payout_hold_days"))),
    )
    db.add(p)
    db.flush()
    return p


def issue_refund(
    db: Session, b: Booking, amount_pence: int, *, reason: str, funded_by: str = "customer_policy",
    actor_id: uuid.UUID | None = None, key: str | None = None,
) -> Refund | None:
    if amount_pence <= 0:
        return None
    pay = booking_payment(db, b.id)
    if pay is None or pay.status not in ("succeeded", "partially_refunded"):
        raise Unprocessable("There is no completed payment to refund.", code="nothing_to_refund")
    already = sum(r.amount_pence for r in db.scalars(select(Refund).where(Refund.booking_id == b.id, Refund.status != "failed")))
    max_refundable = pay.amount_pence + pay.credit_applied_pence - already
    if amount_pence > max_refundable:
        raise Unprocessable(f"At most £{max_refundable / 100:.2f} can still be refunded on this booking.", code="refund_exceeds_paid")
    card_already = sum(r.amount_pence for r in db.scalars(select(Refund).where(Refund.payment_id == pay.id, Refund.status != "failed", Refund.external_id.is_not(None))))
    card_part = min(amount_pence, max(pay.amount_pence - card_already, 0))
    credit_part = amount_pence - card_part
    ref = None
    idem = key or f"refund:{b.id}:{already}:{amount_pence}"
    if card_part > 0:
        ext = get_provider().refund(pay.external_id, card_part, idem)
        ref = Refund(
            payment_id=pay.id, booking_id=b.id, amount_pence=card_part, reason=reason, funded_by=funded_by, external_id=ext,
            status="succeeded", idempotency_key=idem, created_by=actor_id,
        )
        db.add(ref)
    if credit_part > 0:
        db.add(CreditTransaction(user_id=b.customer_id, amount_pence=credit_part, reason="booking_refund", booking_id=b.id))
        prof = db.get(CustomerProfile, b.customer_id)
        prof.credit_pence += credit_part
        if ref is None:
            ref = Refund(
                payment_id=pay.id, booking_id=b.id, amount_pence=credit_part, reason=reason, funded_by=funded_by, external_id=None,
                status="succeeded", idempotency_key=idem, created_by=actor_id,
            )
            db.add(ref)
    pay.status = "refunded" if already + amount_pence >= pay.amount_pence + pay.credit_applied_pence else "partially_refunded"
    db.flush()
    # Keep financials truthful if the booking was already finalised.
    if db.get(BookingFinancial, b.id):
        fin = db.get(BookingFinancial, b.id)
        fin.refunded_pence += amount_pence
        if funded_by == "platform":
            fin.platform_funded_refund_pence += amount_pence
        elif funded_by == "provider":
            payout = db.scalar(select(Payout).where(Payout.booking_id == b.id))
            if payout and payout.status in ("pending", "held"):
                payout.amount_pence = max(payout.amount_pence - amount_pence, 0)
                payout.note = "Reduced after a refund funded by the provider."
                fin.provider_earning_pence = payout.amount_pence
            elif payout and payout.status == "paid":
                # Already paid out: the professional now owes us this amount, netted off their next payouts.
                db.add(ProviderAdjustment(provider_id=payout.provider_id, booking_id=b.id, owed_pence=amount_pence, remaining_pence=amount_pence,
                                          note=f"Refund funded by the professional on {b.reference}, after payout"))
    return ref


def release_due_payouts(db: Session) -> dict:
    """Pay out providers once the hold period ends. Disputed jobs (open complaint or refund request) stay held."""
    from app.models.engagement import Complaint
    from app.models.finance import RefundRequest

    now = utcnow()
    paid = held = failed = 0
    due = db.scalars(select(Payout).where(Payout.status.in_(("pending", "held")), Payout.release_at <= now).with_for_update(skip_locked=True)).all()
    for p in due:
        open_dispute = db.scalar(select(Complaint.id).where(Complaint.booking_id == p.booking_id, Complaint.status.in_(("open", "investigating")))) or \
            db.scalar(select(RefundRequest.id).where(RefundRequest.booking_id == p.booking_id, RefundRequest.status == "open"))
        if open_dispute:
            p.status, p.note = "held", "Held while a complaint or refund request is open."
            held += 1
            continue
        provider = db.get(ProviderProfile, p.provider_id)
        booking = db.get(Booking, p.booking_id)
        # Net off anything this professional owes us from earlier refunds, oldest first.
        net_note = None
        for adj in db.scalars(select(ProviderAdjustment).where(ProviderAdjustment.provider_id == p.provider_id, ProviderAdjustment.remaining_pence > 0).order_by(ProviderAdjustment.created_at)):
            take = min(adj.remaining_pence, p.amount_pence)
            if take <= 0:
                break
            adj.remaining_pence -= take
            p.amount_pence -= take
            net_note = f"£{take / 100:.2f} netted off for an earlier refund ({adj.note})"[:200]
        if p.amount_pence <= 0:
            p.status, p.note = "cancelled", "Nothing payable after adjustments."
            continue
        try:
            p.external_id = get_provider().transfer(provider.stripe_account_id, p.amount_pence, f"payout:{p.id}", booking.reference)
            p.status, p.paid_at, p.note = "paid", now, net_note
            paid += 1
            notify(db, db.get(User, p.provider_id), "payout_paid", "Payout sent",
                   f"Your payout of £{p.amount_pence / 100:.2f} for booking {booking.reference} has been sent.")
        except AppError as exc:
            p.status, p.note = "held", exc.message[:200]
            failed += 1
    return {"paid": paid, "held": held, "failed": failed}
