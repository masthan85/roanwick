import uuid
from datetime import date, time, timedelta

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import delete, func, select

from app.api.auth import _check_password, issue_tokens, TokenOut
from app.core.deps import DB, CurrentUser, Pagination, Provider, audit, paginate
from app.core.errors import Conflict, Forbidden, NotFound, Unprocessable
from app.core.ratelimit import limiter
from app.models.bookings import Booking
from app.models.catalogue import ServiceArea, ServiceOffering
from app.models.engagement import Complaint, Review, SupportTicket
from app.models.finance import Payout
from app.models.providers import (
    AvailabilityException, AvailabilityRule, ProviderArea, ProviderDocument, ProviderProfile, ProviderService,
)
from app.services import accounts, storage
from app.services import bookings as svc
from app.services.config_store import get_setting
from app.services.serialize import booking_out
from app.services.verification import DOC_TYPES, provider_categories, verification_gaps

router = APIRouter(tags=["Service professional"])


class ProviderRegisterIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r"^(\+44|0)[0-9 ]{9,13}$")
    display_name: str = Field(min_length=2, max_length=80)
    accept_terms: bool
    _pw = field_validator("password")(_check_password)

    @field_validator("accept_terms")
    @classmethod
    def _t(cls, v):
        if not v:
            raise ValueError("You need to accept the professional terms to apply.")
        return v


@router.post("/providers/register", status_code=201, response_model=TokenOut, summary="Apply to become a service professional")
@limiter.limit("10/hour")
def register(body: ProviderRegisterIn, request: Request, response: Response, db: DB):
    from app.services.config_store import flag

    if not flag(db, "provider_self_signup"):
        raise Forbidden("We are not taking new applications at the moment.")
    u = accounts.create_user(db, email=body.email, password=body.password, full_name=body.full_name, phone=body.phone, role="provider")
    db.add(ProviderProfile(user_id=u.id, display_name=body.display_name))
    db.flush()
    audit(db, request, u, "provider.applied", "provider", u.id)
    return issue_tokens(db, u, request, response, False)


def _profile(db, user) -> ProviderProfile:
    p = db.get(ProviderProfile, user.id)
    if p is None:
        raise NotFound("Professional profile not found.")
    return p


def profile_out(db, p: ProviderProfile) -> dict:
    return {
        "display_name": p.display_name, "bio": p.bio, "years_experience": p.years_experience, "languages": p.languages, "status": p.status,
        "status_reason": p.status_reason, "accepts_jobs": p.accepts_jobs, "auto_accept": p.auto_accept,
        "offering_ids": [str(s.offering_id) for s in p.services], "areas": sorted(a.outward_code for a in p.areas),
        "rating_avg": float(p.rating_avg), "rating_count": p.rating_count, "jobs_completed": p.jobs_completed,
        "payouts_enabled": p.payouts_enabled, "verification_gaps": verification_gaps(db, p),
    }


@router.get("/provider/profile")
def get_profile(user: Provider, db: DB):
    return profile_out(db, _profile(db, user))


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    bio: str | None = Field(default=None, max_length=1500)
    years_experience: int | None = Field(default=None, ge=0, le=60)
    languages: list[str] | None = None
    accepts_jobs: bool | None = None
    auto_accept: bool | None = None


@router.patch("/provider/profile")
def update_profile(body: ProfileIn, user: Provider, db: DB):
    p = _profile(db, user)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    return profile_out(db, p)


class ServicesIn(BaseModel):
    offering_ids: list[uuid.UUID]


@router.put("/provider/services", summary="Choose the services you offer")
def set_services(body: ServicesIn, user: Provider, db: DB):
    p = _profile(db, user)
    for oid in body.offering_ids:
        o = db.get(ServiceOffering, oid)
        if o is None or not o.is_active or not o.category.is_active:
            raise Unprocessable("One of those services is not open for applications yet.", code="category_not_open")
    p.services = [ProviderService(provider_id=user.id, offering_id=i) for i in set(body.offering_ids)]
    return profile_out(db, p)


class AreasIn(BaseModel):
    outward_codes: list[str]


@router.put("/provider/areas", summary="Choose the postcode districts you cover")
def set_areas(body: AreasIn, user: Provider, db: DB):
    p = _profile(db, user)
    codes = {c.strip().upper() for c in body.outward_codes}
    valid = set(db.scalars(select(ServiceArea.outward_code).where(ServiceArea.outward_code.in_(codes), ServiceArea.is_active.is_(True))))
    if codes - valid:
        raise Unprocessable(f"We do not operate in: {', '.join(sorted(codes - valid))}.", code="area_not_served")
    p.areas = [ProviderArea(provider_id=user.id, outward_code=c) for c in valid]
    return profile_out(db, p)


class RuleIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _order(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time.")
        return self


class AvailabilityIn(BaseModel):
    rules: list[RuleIn]


def _rules_out(db, uid) -> dict:
    rules = db.scalars(select(AvailabilityRule).where(AvailabilityRule.provider_id == uid).order_by(AvailabilityRule.weekday, AvailabilityRule.start_time)).all()
    exc = db.scalars(select(AvailabilityException).where(AvailabilityException.provider_id == uid, AvailabilityException.on_date >= date.today()).order_by(AvailabilityException.on_date)).all()
    return {
        "rules": [{"weekday": r.weekday, "start_time": r.start_time.strftime("%H:%M"), "end_time": r.end_time.strftime("%H:%M")} for r in rules],
        "exceptions": [{"id": str(e.id), "on_date": e.on_date.isoformat(), "start_time": e.start_time.strftime("%H:%M") if e.start_time else None,
                        "end_time": e.end_time.strftime("%H:%M") if e.end_time else None, "is_available": e.is_available, "note": e.note} for e in exc],
    }


@router.get("/provider/availability")
def get_availability(user: Provider, db: DB):
    return _rules_out(db, user.id)


@router.put("/provider/availability", summary="Replace weekly working hours (Europe/London local time)")
def set_availability(body: AvailabilityIn, user: Provider, db: DB):
    by_day: dict[int, list[RuleIn]] = {}
    for r in body.rules:
        by_day.setdefault(r.weekday, []).append(r)
    for rs in by_day.values():
        rs.sort(key=lambda r: r.start_time)
        for a, b in zip(rs, rs[1:]):
            if b.start_time < a.end_time:
                raise Unprocessable("Working hours on the same day cannot overlap.", code="overlapping_hours")
    db.execute(delete(AvailabilityRule).where(AvailabilityRule.provider_id == user.id))
    for r in body.rules:
        db.add(AvailabilityRule(provider_id=user.id, **r.model_dump()))
    db.flush()
    return _rules_out(db, user.id)


class ExceptionIn(BaseModel):
    on_date: date
    start_time: time | None = None
    end_time: time | None = None
    is_available: bool = False
    note: str | None = Field(default=None, max_length=200)


@router.post("/provider/availability/exceptions", status_code=201, summary="Block time off, or add extra hours, on a date")
def add_exception(body: ExceptionIn, user: Provider, db: DB):
    if body.on_date < date.today():
        raise Unprocessable("Choose a date in the future.")
    if (body.start_time is None) != (body.end_time is None) or (body.start_time and body.end_time <= body.start_time):
        raise Unprocessable("Provide both a start and an end time, or neither for the whole day.")
    if body.is_available and body.start_time is None:
        raise Unprocessable("Extra availability needs start and end times.")
    db.add(AvailabilityException(provider_id=user.id, **body.model_dump()))
    db.flush()
    return _rules_out(db, user.id)


@router.delete("/provider/availability/exceptions/{exc_id}", status_code=204)
def remove_exception(exc_id: uuid.UUID, user: Provider, db: DB):
    e = db.get(AvailabilityException, exc_id)
    if e is None or e.provider_id != user.id:
        raise NotFound("Not found.")
    db.delete(e)


# ---------- documents and submission ----------
def doc_out(d: ProviderDocument) -> dict:
    return {"id": str(d.id), "doc_type": d.doc_type, "title": d.title, "status": d.status, "reference": d.reference, "issued_on": d.issued_on,
            "expires_on": d.expires_on, "review_notes": d.review_notes, "original_name": d.original_name, "uploaded_at": d.created_at}


@router.post("/provider/documents", status_code=201, summary="Upload an identity, right-to-work, insurance or qualification document")
def upload_document(
    user: Provider, db: DB, doc_type: str = Form(), title: str = Form(max_length=120), reference: str | None = Form(default=None, max_length=80),
    issued_on: date | None = Form(default=None), expires_on: date | None = Form(default=None), file: UploadFile = File(),
):
    if doc_type not in DOC_TYPES:
        raise Unprocessable(f"Document type must be one of: {', '.join(DOC_TYPES)}.")
    if doc_type == "public_liability" and not expires_on:
        raise Unprocessable("Insurance certificates need an expiry date.", code="expiry_required")
    if expires_on and expires_on < date.today():
        raise Unprocessable("This document has already expired.", code="already_expired")
    key, size, ctype = storage.save_upload(user.id, file)
    d = ProviderDocument(provider_id=user.id, doc_type=doc_type, title=title, storage_key=key, original_name=(file.filename or "upload")[:200],
                         content_type=ctype, size_bytes=size, reference=reference, issued_on=issued_on, expires_on=expires_on)
    db.add(d)
    p = _profile(db, user)
    if p.status == "approved" and doc_type in ("identity", "right_to_work", "public_liability", "dbs"):
        pass  # approved status stays; the new document is reviewed and the old one remains valid until it expires
    db.flush()
    return doc_out(d)


@router.get("/provider/documents")
def list_documents(user: Provider, db: DB):
    return [doc_out(d) for d in db.scalars(select(ProviderDocument).where(ProviderDocument.provider_id == user.id).order_by(ProviderDocument.created_at.desc()))]


@router.delete("/provider/documents/{doc_id}", status_code=204)
def delete_document(doc_id: uuid.UUID, user: Provider, db: DB):
    d = db.get(ProviderDocument, doc_id)
    if d is None or d.provider_id != user.id:
        raise NotFound("Document not found.")
    if d.status != "pending":
        raise Conflict("Reviewed documents are kept for our records.", code="document_locked")
    db.delete(d)


@router.get("/provider/document-alerts", summary="Documents that have expired or are about to")
def doc_alerts(user: Provider, db: DB):
    horizon = date.today() + timedelta(days=int(get_setting(db, "document_expiry_reminder_days")))
    rows = db.scalars(select(ProviderDocument).where(ProviderDocument.provider_id == user.id, ProviderDocument.status == "approved", ProviderDocument.expires_on.is_not(None), ProviderDocument.expires_on <= horizon)).all()
    return [{**doc_out(d), "expired": d.expires_on < date.today()} for d in rows]


@router.get("/provider/checklist", summary="Onboarding progress")
def checklist(user: Provider, db: DB):
    p = _profile(db, user)
    docs = {d.doc_type for d in db.scalars(select(ProviderDocument).where(ProviderDocument.provider_id == user.id))}
    has_rules = db.scalar(select(func.count()).select_from(AvailabilityRule).where(AvailabilityRule.provider_id == user.id)) > 0
    required_docs = {r.document_type for c in provider_categories(db, p) for r in c.requirements if r.is_mandatory}
    items = [
        {"key": "profile", "label": "Write a short profile", "done": bool(p.bio and len(p.bio) >= 30)},
        {"key": "services", "label": "Choose your services", "done": bool(p.services)},
        {"key": "areas", "label": "Choose your coverage areas", "done": bool(p.areas)},
        {"key": "availability", "label": "Set your working hours", "done": has_rules},
        *[{"key": f"doc_{t}", "label": f"Upload: {t.replace('_', ' ')}", "done": t in docs} for t in sorted(required_docs)],
    ]
    return {"items": items, "ready_to_submit": all(i["done"] for i in items) and p.status in ("draft", "rejected"), "status": p.status}


@router.post("/provider/submit", summary="Submit your application for review")
def submit(user: Provider, db: DB, request: Request):
    p = _profile(db, user)
    if p.status not in ("draft", "rejected"):
        raise Conflict("Your application has already been submitted.", code="already_submitted")
    c = checklist(user, db)
    if not all(i["done"] for i in c["items"]):
        raise Unprocessable("Please complete every step in the checklist first.", code="incomplete", details={"items": [i for i in c["items"] if not i["done"]]})
    p.status, p.status_reason = "submitted", None
    audit(db, request, user, "provider.submitted", "provider", user.id)
    return profile_out(db, p)


# ---------- jobs ----------
@router.get("/provider/jobs")
def jobs(user: Provider, db: DB, p: Pagination, status: str | None = None, scope: str = "upcoming"):
    svc.expire_holds(db)
    stmt = select(Booking).where(Booking.provider_id == user.id, Booking.status.notin_(("pending_payment", "expired")))
    if status:
        stmt = stmt.where(Booking.status == status)
    elif scope == "upcoming":
        stmt = stmt.where(Booking.status.in_(("awaiting_provider", "confirmed", "in_progress"))).order_by(Booking.starts_at)
    else:
        stmt = stmt.where(Booking.status.in_(("completed", "cancelled"))).order_by(Booking.starts_at.desc())
    return paginate(db, stmt, p, lambda b: booking_out(db, b, "provider"))


def _job(db, user, jid) -> Booking:
    b = db.scalar(select(Booking).where(Booking.id == jid).with_for_update())
    if b is None or b.provider_id != user.id:
        raise NotFound("Job not found.")
    return b


@router.get("/provider/jobs/{job_id}")
def job(job_id: uuid.UUID, user: Provider, db: DB):
    return booking_out(db, _job(db, user, job_id), "provider")


@router.post("/provider/jobs/{job_id}/accept")
def accept(job_id: uuid.UUID, user: Provider, db: DB):
    b = _job(db, user, job_id)
    svc.provider_accept(db, b, user)
    return booking_out(db, b, "provider")


class DeclineIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.post("/provider/jobs/{job_id}/decline", summary="Decline an offered job, or withdraw from a confirmed one")
def decline(job_id: uuid.UUID, body: DeclineIn, user: Provider, db: DB):
    b = _job(db, user, job_id)
    svc.provider_decline(db, b, user, body.reason)
    return {"ok": True}


@router.post("/provider/jobs/{job_id}/start")
def start(job_id: uuid.UUID, user: Provider, db: DB):
    b = _job(db, user, job_id)
    svc.start_job(db, b, user)
    return booking_out(db, b, "provider")


@router.post("/provider/jobs/{job_id}/complete")
def complete(job_id: uuid.UUID, user: Provider, db: DB):
    b = _job(db, user, job_id)
    svc.complete_job(db, b, user)
    return booking_out(db, b, "provider")


# ---------- earnings, reviews, metrics ----------
@router.get("/provider/earnings")
def earnings(user: Provider, db: DB, p: Pagination):
    def total(*statuses):
        return db.scalar(select(func.coalesce(func.sum(Payout.amount_pence), 0)).where(Payout.provider_id == user.id, Payout.status.in_(statuses)))

    stmt = select(Payout).where(Payout.provider_id == user.id).order_by(Payout.created_at.desc())

    def conv(po):
        b = db.get(Booking, po.booking_id)
        return {"id": str(po.id), "booking_reference": b.reference, "completed_at": b.completed_at, "service_value_pence": po.gross_pence,
                "commission_pence": po.commission_pence, "net_pence": po.amount_pence, "status": po.status, "release_at": po.release_at, "paid_at": po.paid_at, "note": po.note}

    return {"paid_pence": total("paid"), "pending_pence": total("pending", "held"), "commission_bps": int(get_setting(db, "commission_bps")),
            "payouts": paginate(db, stmt, p, conv)}


@router.get("/provider/reviews")
def my_reviews(user: Provider, db: DB):
    rows = db.scalars(select(Review).where(Review.provider_id == user.id).order_by(Review.created_at.desc()).limit(50)).all()
    return [{"id": str(r.id), "rating": r.rating, "punctuality": r.punctuality, "comment": r.comment, "reply": r.provider_reply, "created_at": r.created_at} for r in rows]


class ReplyIn(BaseModel):
    reply: str = Field(min_length=2, max_length=1000)


@router.post("/provider/reviews/{review_id}/reply", status_code=204)
def reply(review_id: uuid.UUID, body: ReplyIn, user: Provider, db: DB):
    r = db.get(Review, review_id)
    if r is None or r.provider_id != user.id:
        raise NotFound("Review not found.")
    r.provider_reply = body.reply


@router.get("/provider/metrics", summary="Quality metrics used for matching and reviews of performance")
def metrics(user: Provider, db: DB):
    p = _profile(db, user)
    started = db.scalar(select(func.count()).select_from(Booking).where(Booking.provider_id == user.id, Booking.started_at.is_not(None)))
    late = db.scalar(select(func.count()).select_from(Booking).where(Booking.provider_id == user.id, Booking.arrived_late.is_(True)))
    repeat = db.execute(select(Booking.customer_id).where(Booking.provider_id == user.id, Booking.status == "completed").group_by(Booking.customer_id).having(func.count() > 1)).all()
    customers = db.scalar(select(func.count(func.distinct(Booking.customer_id))).where(Booking.provider_id == user.id, Booking.status == "completed"))
    complaints = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.provider_id == user.id))
    done = p.jobs_completed
    return {
        "rating_avg": float(p.rating_avg), "rating_count": p.rating_count, "jobs_completed": done,
        "on_time_rate": None if not started else round(1 - late / started, 3), "cancellations": p.cancel_count,
        "repeat_customer_rate": None if not customers else round(len(repeat) / customers, 3),
        "complaints": complaints, "complaints_per_100_jobs": None if not done else round(complaints * 100 / done, 1),
    }


class TicketIn(BaseModel):
    kind: str = Field(default="general", pattern="^(general|provider_dispute|payout|account)$")
    subject: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=10, max_length=3000)
    booking_id: uuid.UUID | None = None


@router.post("/support/tickets", status_code=201, summary="Contact support or raise a dispute")
def ticket(body: TicketIn, user: CurrentUser, db: DB):
    t = SupportTicket(user_id=user.id, contact_email=user.email, **body.model_dump())
    db.add(t)
    db.flush()
    return {"id": str(t.id), "reference": str(t.id)[:8].upper()}


@router.get("/support/tickets")
def my_tickets(user: CurrentUser, db: DB):
    rows = db.scalars(select(SupportTicket).where(SupportTicket.user_id == user.id).order_by(SupportTicket.created_at.desc())).all()
    return [{"id": str(t.id), "reference": str(t.id)[:8].upper(), "kind": t.kind, "subject": t.subject, "status": t.status, "response": t.response, "created_at": t.created_at} for t in rows]
