import uuid
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.db import utcnow
from app.core.deps import DB, Customer, CurrentUser, Pagination, paginate
from app.core.errors import Conflict, Forbidden, NotFound, Unprocessable
from app.models.bookings import Booking, FavouriteProvider, Subscription
from app.models.catalogue import Quotation, ServiceOffering
from app.models.engagement import Complaint, CreditTransaction, Notification, Review
from app.models.finance import Payment, Refund, RefundRequest
from app.models.identity import Address, CustomerProfile
from app.models.providers import ProviderProfile
from app.services import bookings as svc
from app.services import payment_events, recurring
from app.services.config_store import flag, get_setting
from app.services.idempotency import run_idempotent
from app.services.notify import notify
from app.services.payments import get_provider
from app.services.postcodes import normalise_postcode
from app.services.serialize import booking_out, pro_public

router = APIRouter(tags=["Customer"])


# ---------- addresses ----------
class AddressIn(BaseModel):
    label: str = Field(default="Home", max_length=40)
    line1: str = Field(min_length=3, max_length=120)
    line2: str | None = Field(default=None, max_length=120)
    city: str = Field(default="London", max_length=80)
    postcode: str
    bedrooms: int | None = Field(default=None, ge=0, le=10)
    access_notes: str | None = Field(default=None, max_length=500)
    is_default: bool = False


def address_out(a: Address) -> dict:
    return {"id": str(a.id), "label": a.label, "line1": a.line1, "line2": a.line2, "city": a.city, "postcode": a.postcode,
            "bedrooms": a.bedrooms, "access_notes": a.access_notes, "is_default": a.is_default}


@router.get("/addresses")
def list_addresses(user: Customer, db: DB):
    return [address_out(a) for a in db.scalars(select(Address).where(Address.user_id == user.id).order_by(Address.created_at))]


@router.post("/addresses", status_code=201)
def add_address(body: AddressIn, user: Customer, db: DB):
    pc, outward = normalise_postcode(body.postcode)
    first = db.scalar(select(func.count()).select_from(Address).where(Address.user_id == user.id)) == 0
    a = Address(user_id=user.id, **{**body.model_dump(exclude={"postcode", "is_default"}), "postcode": pc, "outward_code": outward}, is_default=body.is_default or first)
    if a.is_default:
        for o in db.scalars(select(Address).where(Address.user_id == user.id)):
            o.is_default = False
    db.add(a)
    db.flush()
    return address_out(a)


def _own_address(db, user, aid) -> Address:
    a = db.get(Address, aid)
    if a is None or a.user_id != user.id:
        raise NotFound("Address not found.")
    return a


@router.put("/addresses/{address_id}")
def update_address(address_id: uuid.UUID, body: AddressIn, user: Customer, db: DB):
    a = _own_address(db, user, address_id)
    pc, outward = normalise_postcode(body.postcode)
    for k, v in body.model_dump(exclude={"postcode", "is_default"}).items():
        setattr(a, k, v)
    a.postcode, a.outward_code = pc, outward
    if body.is_default:
        for o in db.scalars(select(Address).where(Address.user_id == user.id, Address.id != a.id)):
            o.is_default = False
        a.is_default = True
    return address_out(a)


@router.delete("/addresses/{address_id}", status_code=204)
def delete_address(address_id: uuid.UUID, user: Customer, db: DB):
    a = _own_address(db, user, address_id)
    if db.scalar(select(Booking.id).where(Booking.address_snapshot["postcode"].astext == a.postcode, Booking.customer_id == user.id, Booking.status.in_(svc.BLOCKING_STATUSES))):
        raise Conflict("This address has upcoming bookings.", code="address_in_use")
    if db.scalar(select(Subscription.id).where(Subscription.address_id == a.id, Subscription.status != "cancelled")):
        raise Conflict("This address is used by a recurring plan.", code="address_in_use")
    db.delete(a)


# ---------- bookings ----------
class BookingIn(BaseModel):
    quotation_id: uuid.UUID
    address_id: uuid.UUID
    starts_at: datetime
    provider_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=500)
    use_credit: bool = False
    accept_terms: bool


class PayIn(BaseModel):
    payment_method: str = Field(max_length=80)


def _own_booking(db, user, bid, lock=False) -> Booking:
    stmt = select(Booking).where(Booking.id == bid)
    if lock:
        stmt = stmt.with_for_update()
    b = db.scalar(stmt)
    if b is None or b.customer_id != user.id:
        raise NotFound("Booking not found.")
    return b


@router.post("/bookings", status_code=201, summary="Create a booking and hold the slot (payment follows)")
def create_booking(body: BookingIn, user: Customer, db: DB, idempotency_key: str | None = Header(default=None, max_length=80)):
    if not body.accept_terms:
        raise Unprocessable("Please accept the terms and the cancellation policy to continue.", code="terms_required")
    if body.starts_at.tzinfo is None:
        raise Unprocessable("starts_at must include a timezone offset.", code="naive_datetime")

    def run():
        q = db.get(Quotation, body.quotation_id)
        if q is None:
            raise NotFound("Quotation not found.")
        a = _own_address(db, user, body.address_id)
        b = svc.create_booking(db, customer=user, quotation=q, address=a, starts_at=body.starts_at.astimezone(svc.avail.ZoneInfo("UTC")),
                               provider_id=body.provider_id, notes=body.notes, use_credit=body.use_credit, idempotency_key=idempotency_key)
        return _json(booking_out(db, b))

    return run_idempotent(db, f"booking:{user.id}", idempotency_key, body.model_dump(mode="json"), run)


def _json(d: dict) -> dict:
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(d)


@router.post("/bookings/{booking_id}/pay", summary="Pay for a held booking (sandbox card tokens in test mode)")
def pay(booking_id: uuid.UUID, body: PayIn, user: Customer, db: DB, idempotency_key: str | None = Header(default=None, max_length=80)):
    b = _own_booking(db, user, booking_id, lock=True)
    prov = get_provider()
    if prov.name != "sandbox":
        raise Unprocessable("Payment is confirmed in the browser with Stripe. Use the client secret from the booking.", code="client_side_payment")

    def run():
        svc.expire_holds(db)
        if b.status not in ("pending_payment", "awaiting_provider", "confirmed"):
            raise Conflict("This booking is no longer waiting for payment.", code="not_payable")
        pay_ = db.scalar(select(Payment).where(Payment.booking_id == b.id).order_by(Payment.created_at.desc()))
        if pay_.status == "succeeded":
            return {"ok": True, "booking": _json(booking_out(db, b))}
        event = prov.confirm(pay_.external_id, body.payment_method, pay_.amount_pence)
        payment_events.process_event(db, event, prov.name)
        db.refresh(pay_)
        db.refresh(b)
        return {"ok": pay_.status == "succeeded", "error": pay_.failure_message, "booking": _json(booking_out(db, b))}

    result = run_idempotent(db, f"pay:{user.id}", idempotency_key, {"b": str(booking_id), "pm": body.payment_method}, run)
    if not result["ok"]:
        return JSONResponse(status_code=402, content={"error": {"code": "payment_failed", "message": result["error"] or "Payment failed.", "details": {"booking": result["booking"]}}})
    return result["booking"]


@router.get("/bookings")
def list_bookings(user: Customer, db: DB, p: Pagination, status: str | None = None, upcoming: bool | None = None):
    svc.expire_holds(db)
    stmt = select(Booking).where(Booking.customer_id == user.id, Booking.status != "expired")
    if status:
        stmt = stmt.where(Booking.status == status)
    if upcoming is True:
        stmt = stmt.where(Booking.starts_at >= utcnow(), Booking.status.in_(("pending_payment", "awaiting_provider", "confirmed", "in_progress")))
    if upcoming is False:
        stmt = stmt.where((Booking.starts_at < utcnow()) | Booking.status.in_(("completed", "cancelled")))
    stmt = stmt.order_by(Booking.starts_at.desc() if upcoming is not True else Booking.starts_at.asc())
    return paginate(db, stmt, p, lambda b: booking_out(db, b))


@router.get("/bookings/{booking_id}")
def get_booking(booking_id: uuid.UUID, user: Customer, db: DB):
    return booking_out(db, _own_booking(db, user, booking_id))


class CancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.post("/bookings/{booking_id}/cancel")
def cancel(booking_id: uuid.UUID, body: CancelIn, user: Customer, db: DB):
    b = _own_booking(db, user, booking_id, lock=True)
    result = svc.cancel_booking(db, b, user, "customer", body.reason)
    return {**result, "booking": booking_out(db, b)}


@router.get("/bookings/{booking_id}/cancellation-preview")
def preview(booking_id: uuid.UUID, user: Customer, db: DB):
    return svc.refund_preview(db, _own_booking(db, user, booking_id))


class RescheduleIn(BaseModel):
    starts_at: datetime
    allow_other_professional: bool = False


@router.post("/bookings/{booking_id}/reschedule")
def reschedule(booking_id: uuid.UUID, body: RescheduleIn, user: Customer, db: DB):
    b = _own_booking(db, user, booking_id, lock=True)
    if body.starts_at.tzinfo is None:
        raise Unprocessable("starts_at must include a timezone offset.", code="naive_datetime")
    svc.reschedule(db, b, user, body.starts_at.astimezone(svc.avail.ZoneInfo("UTC")), body.allow_other_professional)
    return booking_out(db, b)


# ---------- reviews, complaints, refund requests ----------
class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    punctuality: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1500)


@router.post("/bookings/{booking_id}/review", status_code=201)
def review(booking_id: uuid.UUID, body: ReviewIn, user: Customer, db: DB):
    b = _own_booking(db, user, booking_id)
    if b.status != "completed" or not b.provider_id:
        raise Conflict("You can review a booking once it has been completed.", code="not_completed")
    if db.scalar(select(Review.id).where(Review.booking_id == b.id)):
        raise Conflict("You have already reviewed this booking.", code="already_reviewed")
    r = Review(booking_id=b.id, customer_id=user.id, provider_id=b.provider_id, **body.model_dump())
    db.add(r)
    db.flush()
    prof = db.get(ProviderProfile, b.provider_id)
    avg, cnt = db.execute(select(func.avg(Review.rating), func.count()).where(Review.provider_id == b.provider_id, Review.is_published.is_(True))).one()
    prof.rating_avg, prof.rating_count = round(float(avg or 0), 2), cnt
    notify(db, db.get(type(user), b.provider_id), "new_review", f"New {body.rating}-star review", body.comment or "A customer left you a rating.", ("in_app",))
    return {"id": str(r.id)}


class ComplaintIn(BaseModel):
    category: str = Field(pattern="^(quality|lateness|no_show|damage|conduct|safety|other)$")
    description: str = Field(min_length=10, max_length=2000)


@router.post("/bookings/{booking_id}/complaints", status_code=201)
def complain(booking_id: uuid.UUID, body: ComplaintIn, user: Customer, db: DB):
    b = _own_booking(db, user, booking_id)
    if b.status not in ("completed", "in_progress", "cancelled"):
        raise Conflict("You can raise a complaint once the visit has started.", code="too_early")
    c = Complaint(booking_id=b.id, customer_id=user.id, provider_id=b.provider_id, category=body.category, description=body.description,
                  severity="high" if body.category in ("safety", "damage", "conduct", "no_show") else "normal")
    db.add(c)
    db.flush()
    if b.provider_id:
        from app.services import quality

        quality.evaluate(db, b.provider_id)
    notify(db, user, "complaint_received", "We have received your complaint",
           f"Reference {str(c.id)[:8].upper()}. We aim to respond within {get_setting(db, 'complaint_sla_hours')} hours.", ("in_app", "email"))
    return {"id": str(c.id), "reference": str(c.id)[:8].upper(), "status": c.status}


@router.get("/complaints")
def my_complaints(user: Customer, db: DB):
    rows = db.scalars(select(Complaint).where(Complaint.customer_id == user.id).order_by(Complaint.created_at.desc())).all()
    return [{"id": str(c.id), "reference": str(c.id)[:8].upper(), "booking_id": str(c.booking_id), "category": c.category, "status": c.status,
             "description": c.description, "resolution": c.resolution, "created_at": c.created_at} for c in rows]


class RefundRequestIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)
    requested_pence: int | None = Field(default=None, ge=1)


@router.post("/bookings/{booking_id}/refund-requests", status_code=201)
def request_refund(booking_id: uuid.UUID, body: RefundRequestIn, user: Customer, db: DB):
    b = _own_booking(db, user, booking_id)
    if b.status not in ("completed", "cancelled"):
        raise Conflict("Refund requests can be made after a visit is completed or cancelled.", code="too_early")
    if body.requested_pence and body.requested_pence > b.total_pence:
        raise Unprocessable("That is more than you paid.", code="refund_exceeds_paid")
    if db.scalar(select(RefundRequest.id).where(RefundRequest.booking_id == b.id, RefundRequest.status == "open")):
        raise Conflict("You already have an open refund request for this booking.", code="duplicate")
    r = RefundRequest(booking_id=b.id, customer_id=user.id, reason=body.reason, requested_pence=body.requested_pence)
    db.add(r)
    db.flush()
    return {"id": str(r.id), "status": r.status}


@router.get("/refund-requests")
def my_refund_requests(user: Customer, db: DB):
    rows = db.scalars(select(RefundRequest).where(RefundRequest.customer_id == user.id).order_by(RefundRequest.created_at.desc())).all()
    return [{"id": str(r.id), "booking_id": str(r.booking_id), "status": r.status, "reason": r.reason, "approved_pence": r.approved_pence, "decision_note": r.decision_note, "created_at": r.created_at} for r in rows]


# ---------- favourites ----------
@router.get("/favourites")
def favourites(user: Customer, db: DB):
    ids = db.scalars(select(FavouriteProvider.provider_id).where(FavouriteProvider.customer_id == user.id)).all()
    return [pro_public(db, db.get(ProviderProfile, i)) for i in ids if db.get(ProviderProfile, i)]


@router.put("/favourites/{provider_id}", status_code=204)
def add_favourite(provider_id: uuid.UUID, user: Customer, db: DB):
    served = db.scalar(select(Booking.id).where(Booking.customer_id == user.id, Booking.provider_id == provider_id, Booking.status == "completed"))
    if not served:
        raise Forbidden("You can save a professional after they have completed a visit for you.")
    if not db.get(FavouriteProvider, (user.id, provider_id)):
        db.add(FavouriteProvider(customer_id=user.id, provider_id=provider_id))


@router.delete("/favourites/{provider_id}", status_code=204)
def remove_favourite(provider_id: uuid.UUID, user: Customer, db: DB):
    f = db.get(FavouriteProvider, (user.id, provider_id))
    if f:
        db.delete(f)


@router.post("/bookings/{booking_id}/rebook-quote", summary="Pre-fill a repeat booking with the same professional")
def rebook_info(booking_id: uuid.UUID, user: Customer, db: DB):
    b = _own_booking(db, user, booking_id)
    return {"offering_id": str(b.offering_id), "offering_slug": db.get(ServiceOffering, b.offering_id).slug, "provider_id": str(b.provider_id) if b.provider_id else None,
            "inputs": b.inputs, "address_postcode": b.address_snapshot.get("postcode")}


# ---------- subscriptions ----------
class SubscriptionIn(BaseModel):
    offering_id: uuid.UUID
    address_id: uuid.UUID
    frequency: str = Field(pattern="^(weekly|fortnightly)$")
    first_visit_on: date
    start_time: time
    minutes: int | None = None
    addons: list[str] = []
    preferred_provider_id: uuid.UUID | None = None
    payment_method: str = Field(default="pm_card_visa", max_length=80)
    accept_terms: bool


def sub_out(db, s: Subscription) -> dict:
    nxt = db.scalars(select(Booking).where(Booking.subscription_id == s.id, Booking.status.in_(("confirmed", "awaiting_provider", "pending_payment")), Booking.starts_at >= utcnow()).order_by(Booking.starts_at).limit(3)).all()
    pro = db.get(ProviderProfile, s.preferred_provider_id) if s.preferred_provider_id else None
    return {"id": str(s.id), "offering": db.get(ServiceOffering, s.offering_id).name, "frequency": s.frequency, "weekday": s.weekday,
            "start_time": s.start_time.strftime("%H:%M"), "duration_minutes": s.duration_minutes, "status": s.status,
            "preferred_professional": pro_public(db, pro) if pro else None, "skipped_dates": s.skipped_dates,
            "upcoming": [{"id": str(b.id), "reference": b.reference, "starts_at": b.starts_at, "status": b.status} for b in nxt]}


@router.post("/subscriptions", status_code=201, summary="Start a recurring plan")
def create_subscription(body: SubscriptionIn, user: Customer, db: DB):
    if not flag(db, "recurring_plans"):
        raise Unprocessable("Recurring plans are not available at the moment.", code="feature_off")
    if not body.accept_terms:
        raise Unprocessable("Please accept the terms and the plan conditions.", code="terms_required")
    a = _own_address(db, user, body.address_id)
    o = db.get(ServiceOffering, body.offering_id)
    if o is None or not o.supports_recurring:
        raise Unprocessable("That service cannot be booked as a plan.")
    from app.services.pricing import build_quote

    sp = db.begin_nested()
    q = build_quote(db, user=user, offering_id=o.id, postcode=a.postcode, minutes=body.minutes, bedrooms=a.bedrooms if o.pricing_model == "tiered" else None,
                    addon_codes=body.addons, frequency=body.frequency)
    duration = q.duration_minutes
    sp.rollback()
    if body.first_visit_on < utcnow().date():
        raise Unprocessable("Choose a first visit date in the future.")
    s = Subscription(customer_id=user.id, offering_id=o.id, address_id=a.id, preferred_provider_id=body.preferred_provider_id, frequency=body.frequency,
                     weekday=body.first_visit_on.weekday(), start_time=body.start_time, duration_minutes=duration, addon_codes=body.addons,
                     next_visit_on=body.first_visit_on, payment_method_ref=body.payment_method)
    db.add(s)
    db.flush()
    result = recurring.generate_visits(db, s)
    horizon = utcnow().date() + timedelta(days=int(get_setting(db, "plan_horizon_days")))
    if result["created"] == 0 and body.first_visit_on <= horizon:
        raise Conflict("We could not schedule the first visit at that time. Please try another day or time.", code="no_availability")
    note = None if result["created"] else f"Your first visit is more than {get_setting(db, 'plan_horizon_days')} days away, so we will schedule and charge it closer to the date."
    return {**sub_out(db, s), "generation": result, "note": note}


@router.get("/subscriptions")
def list_subscriptions(user: Customer, db: DB):
    return [sub_out(db, s) for s in db.scalars(select(Subscription).where(Subscription.customer_id == user.id, Subscription.status != "cancelled").order_by(Subscription.created_at.desc()))]


class SubActionIn(BaseModel):
    action: str = Field(pattern="^(pause|resume|cancel|skip)$")
    skip_date: date | None = None


@router.post("/subscriptions/{sub_id}/actions")
def sub_action(sub_id: uuid.UUID, body: SubActionIn, user: Customer, db: DB):
    s = db.get(Subscription, sub_id)
    if s is None or s.customer_id != user.id:
        raise NotFound("Plan not found.")
    if body.action == "pause":
        s.status = "paused"
    elif body.action == "resume":
        s.status = "active"
        recurring.generate_visits(db, s)
    elif body.action == "skip":
        if not body.skip_date:
            raise Unprocessable("Choose the date to skip.")
        s.skipped_dates = [*s.skipped_dates, body.skip_date.isoformat()]
        for b in db.scalars(select(Booking).where(Booking.subscription_id == s.id, Booking.status.in_(("confirmed", "awaiting_provider")))):
            if svc.avail.local(b.starts_at).date() == body.skip_date:
                svc.cancel_booking(db, b, user, "customer", "Skipped visit")
    else:
        s.status, s.cancelled_at = "cancelled", utcnow()
        for b in db.scalars(select(Booking).where(Booking.subscription_id == s.id, Booking.status.in_(("confirmed", "awaiting_provider", "pending_payment")), Booking.starts_at > utcnow())):
            svc.cancel_booking(db, b, user, "customer", "Plan cancelled")
    return sub_out(db, s)


# ---------- credit, referrals, payments, notifications ----------
@router.get("/me/referral")
def referral(user: Customer, db: DB):
    prof = db.get(CustomerProfile, user.id)
    from app.core.config import get_settings

    referred = db.scalar(select(func.count()).select_from(CustomerProfile).where(CustomerProfile.referred_by_user_id == user.id))
    return {"code": prof.referral_code, "credit_pence": prof.credit_pence, "referred_count": referred,
            "reward_pence": get_setting(db, "referral_reward_pence"), "welcome_pence": get_setting(db, "referral_welcome_pence"),
            "share_url": f"{get_settings().public_web_url}/signup?ref={prof.referral_code}",
            "transactions": [{"amount_pence": t.amount_pence, "reason": t.reason, "at": t.created_at} for t in db.scalars(select(CreditTransaction).where(CreditTransaction.user_id == user.id).order_by(CreditTransaction.created_at.desc()).limit(20))]}


@router.get("/payments")
def payment_history(user: Customer, db: DB, p: Pagination):
    stmt = select(Payment).where(Payment.customer_id == user.id, Payment.status != "cancelled").order_by(Payment.created_at.desc())

    def conv(pay):
        b = db.get(Booking, pay.booking_id)
        refunds = db.scalars(select(Refund).where(Refund.payment_id == pay.id)).all()
        return {"id": str(pay.id), "booking_reference": b.reference, "booking_id": str(b.id), "amount_pence": pay.amount_pence, "credit_applied_pence": pay.credit_applied_pence,
                "status": pay.status, "paid_at": pay.paid_at, "created_at": pay.created_at, "refunded_pence": sum(r.amount_pence for r in refunds)}

    return paginate(db, stmt, p, conv)


@router.get("/notifications")
def notifications(user: CurrentUser, db: DB, p: Pagination):
    stmt = select(Notification).where(Notification.user_id == user.id, Notification.channel == "in_app").order_by(Notification.created_at.desc())
    unread = db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.channel == "in_app", Notification.read_at.is_(None)))
    res = paginate(db, stmt, p, lambda n: {"id": str(n.id), "subject": n.subject, "body": n.body, "created_at": n.created_at, "read": n.read_at is not None, "template": n.template})
    return {**res, "unread": unread}


@router.post("/notifications/read-all", status_code=204)
def read_all(user: CurrentUser, db: DB):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.channel == "in_app", Notification.read_at.is_(None))):
        n.read_at = utcnow()
