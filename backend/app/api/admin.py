import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, or_, select

from app.api.auth import _check_password
from app.core.db import utcnow
from app.core.deps import DB, Pagination, audit, paginate, require_permission, user_permissions
from app.core.errors import Conflict, Forbidden, NotFound, Unprocessable
from app.models.bookings import Booking
from app.models.engagement import Complaint, SupportTicket
from app.models.finance import Payout, RefundRequest
from app.models.identity import Role, User
from app.models.providers import ProviderDocument, ProviderProfile
from app.services import accounts, finance, storage
from app.services import bookings as svc
from app.services.availability import rank_candidates
from app.services.notify import notify
from app.services.serialize import booking_out
from app.services.verification import verification_gaps

router = APIRouter(prefix="/admin", tags=["Administration"])


def perm(*keys: str):
    return Depends(require_permission(*keys))


# ---------- customers and users ----------
@router.get("/users")
def users(db: DB, p: Pagination, actor: User = perm("users.read"), role: str | None = None, q: str | None = None):
    stmt = select(User).order_by(User.created_at.desc())
    if role:
        stmt = stmt.where(User.roles.any(Role.key == role))
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), User.full_name.ilike(f"%{q}%")))

    def conv(u: User):
        return {"id": str(u.id), "email": u.email, "full_name": u.full_name, "phone": u.phone, "roles": u.role_keys, "is_active": u.is_active,
                "created_at": u.created_at, "last_login_at": u.last_login_at}

    return paginate(db, stmt, p, conv)


@router.get("/users/{user_id}", summary="Customer or staff detail with booking, complaint and credit history")
def user_detail(user_id: uuid.UUID, db: DB, actor: User = perm("users.read")):
    from app.models.engagement import CreditTransaction
    from app.models.identity import Address, CustomerProfile

    u = db.get(User, user_id)
    if u is None:
        raise NotFound("User not found.")
    prof = db.get(CustomerProfile, u.id)
    bookings_ = db.scalars(select(Booking).where(Booking.customer_id == u.id).order_by(Booking.starts_at.desc()).limit(25)).all()
    spent = db.scalar(select(func.coalesce(func.sum(Booking.total_pence), 0)).where(Booking.customer_id == u.id, Booking.status == "completed"))
    complaints_ = db.scalars(select(Complaint).where(Complaint.customer_id == u.id).order_by(Complaint.created_at.desc()).limit(10)).all()
    out = {
        "id": str(u.id), "email": u.email, "full_name": u.full_name, "phone": u.phone, "roles": u.role_keys, "is_active": u.is_active,
        "created_at": u.created_at, "last_login_at": u.last_login_at, "email_verified": u.email_verified_at is not None, "mfa_enabled": u.mfa_enabled_at is not None,
        "marketing_consent": u.marketing_consent, "anonymised": u.anonymised_at is not None,
        "bookings": [{"id": str(b.id), "reference": b.reference, "starts_at": b.starts_at, "status": b.status, "total_pence": b.total_pence} for b in bookings_],
        "completed_spend_pence": int(spent), "complaints": [{"id": str(c.id), "category": c.category, "status": c.status, "created_at": c.created_at} for c in complaints_],
    }
    if prof:
        out["customer"] = {
            "referral_code": prof.referral_code, "acquisition_source": prof.acquisition_source, "credit_pence": prof.credit_pence,
            "addresses": [{"postcode": a.postcode, "label": a.label} for a in db.scalars(select(Address).where(Address.user_id == u.id))],
            "credit_history": [{"amount_pence": t.amount_pence, "reason": t.reason, "at": t.created_at} for t in db.scalars(select(CreditTransaction).where(CreditTransaction.user_id == u.id).order_by(CreditTransaction.created_at.desc()).limit(10))],
        }
    return out


class StatusIn(BaseModel):
    is_active: bool
    reason: str = Field(min_length=3, max_length=300)


@router.post("/users/{user_id}/status")
def set_user_status(user_id: uuid.UUID, body: StatusIn, request: Request, db: DB, actor: User = perm("users.manage")):
    u = db.get(User, user_id)
    if u is None:
        raise NotFound("User not found.")
    if u.id == actor.id:
        raise Unprocessable("You cannot change your own status.")
    before = {"is_active": u.is_active}
    u.is_active = body.is_active
    audit(db, request, actor, "user.status_changed", "user", u.id, before, {"is_active": body.is_active, "reason": body.reason})
    return {"id": str(u.id), "is_active": u.is_active}


class StaffIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str
    role: str = Field(pattern="^(super_admin|operations|support|finance)$")

    _pw = field_validator("password")(_check_password)


@router.post("/staff", status_code=201)
def create_staff(body: StaffIn, request: Request, db: DB, actor: User = perm("staff.manage")):
    u = accounts.create_user(db, email=body.email, password=body.password, full_name=body.full_name, phone=None, role=body.role)
    u.email_verified_at = utcnow()
    audit(db, request, actor, "staff.created", "user", u.id, None, {"role": body.role, "email": u.email})
    return {"id": str(u.id), "email": u.email, "role": body.role}


# ---------- providers and verification ----------
def _prov_row(db, p: ProviderProfile) -> dict:
    u = db.get(User, p.user_id)
    return {"id": str(p.user_id), "display_name": p.display_name, "email": u.email, "phone": u.phone, "status": p.status, "rating_avg": float(p.rating_avg),
            "rating_count": p.rating_count, "jobs_completed": p.jobs_completed, "created_at": p.created_at, "cancel_count": p.cancel_count, "late_count": p.late_count}


@router.get("/providers")
def providers(db: DB, p: Pagination, actor: User = perm("users.read"), status: str | None = None, q: str | None = None):
    stmt = select(ProviderProfile).order_by(ProviderProfile.created_at.desc())
    if status:
        stmt = stmt.where(ProviderProfile.status == status)
    if q:
        stmt = stmt.where(ProviderProfile.display_name.ilike(f"%{q}%"))
    return paginate(db, stmt, p, lambda x: _prov_row(db, x))


@router.get("/providers/{pid}")
def provider_detail(pid: uuid.UUID, db: DB, actor: User = perm("providers.review")):
    p = db.get(ProviderProfile, pid)
    if p is None:
        raise NotFound("Provider not found.")
    docs = db.scalars(select(ProviderDocument).where(ProviderDocument.provider_id == pid).order_by(ProviderDocument.created_at.desc())).all()
    return {
        **_prov_row(db, p), "bio": p.bio, "years_experience": p.years_experience, "languages": p.languages, "status_reason": p.status_reason,
        "commission_override_bps": p.commission_override_bps, "auto_accept": p.auto_accept, "areas": sorted(a.outward_code for a in p.areas),
        "offering_ids": [str(s.offering_id) for s in p.services], "verification_gaps": verification_gaps(db, p),
        "documents": [{"id": str(d.id), "doc_type": d.doc_type, "title": d.title, "status": d.status, "reference": d.reference, "issued_on": d.issued_on,
                       "expires_on": d.expires_on, "review_notes": d.review_notes, "original_name": d.original_name, "uploaded_at": d.created_at} for d in docs],
    }


@router.get("/documents/{doc_id}/download")
def download_document(doc_id: uuid.UUID, request: Request, db: DB, actor: User = perm("providers.review")):
    d = db.get(ProviderDocument, doc_id)
    if d is None:
        raise NotFound("Document not found.")
    audit(db, request, actor, "document.viewed", "provider_document", d.id)
    return Response(storage.read_file(d.storage_key), media_type=d.content_type, headers={"Content-Disposition": f'inline; filename="{d.original_name}"', "Cache-Control": "no-store"})


class DocReviewIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    notes: str | None = Field(default=None, max_length=300)


@router.post("/documents/{doc_id}/review")
def review_document(doc_id: uuid.UUID, body: DocReviewIn, request: Request, db: DB, actor: User = perm("providers.review")):
    d = db.get(ProviderDocument, doc_id)
    if d is None:
        raise NotFound("Document not found.")
    if body.decision == "reject" and not body.notes:
        raise Unprocessable("Please say why the document was rejected so the professional can fix it.", code="notes_required")
    before = {"status": d.status}
    d.status = "approved" if body.decision == "approve" else "rejected"
    d.review_notes, d.reviewed_by, d.reviewed_at = body.notes, actor.id, utcnow()
    audit(db, request, actor, f"document.{d.status}", "provider_document", d.id, before, {"status": d.status, "doc_type": d.doc_type, "provider": str(d.provider_id)})
    notify(db, db.get(User, d.provider_id), "document_reviewed", f"Your {d.title} was {d.status}", body.notes or "Thank you. Your document has been checked.")
    return {"id": str(d.id), "status": d.status}


class DecisionIn(BaseModel):
    action: str = Field(pattern="^(approve|reject|suspend|reinstate)$")
    reason: str | None = Field(default=None, max_length=300)


@router.post("/providers/{pid}/decision", summary="Approve, reject, suspend or reinstate a professional")
def decide(pid: uuid.UUID, body: DecisionIn, request: Request, db: DB, actor: User = perm("providers.review")):
    p = db.get(ProviderProfile, pid)
    if p is None:
        raise NotFound("Provider not found.")
    before = {"status": p.status}
    if body.action in ("approve", "reinstate"):
        if p.status not in ("submitted", "suspended", "rejected"):
            raise Conflict("This professional is not waiting for a decision.", code="invalid_transition")
        gaps = {k: v for k, v in verification_gaps(db, p).items() if v}
        if gaps or not p.services:
            raise Unprocessable(
                "This professional cannot be approved until every mandatory document is approved and in date.", code="verification_incomplete",
                details={"missing": gaps or {"services": ["No services selected"]}},
            )
        p.status, p.approved_at, p.approved_by, p.status_reason = "approved", utcnow(), actor.id, None
    else:
        if body.action == "reject" and p.status != "submitted":
            raise Conflict("Only submitted applications can be rejected.", code="invalid_transition")
        if body.action == "suspend" and p.status != "approved":
            raise Conflict("Only approved professionals can be suspended.", code="invalid_transition")
        if not body.reason:
            raise Unprocessable("A reason is required.", code="reason_required")
        p.status, p.status_reason = ("rejected" if body.action == "reject" else "suspended"), body.reason
    audit(db, request, actor, f"provider.{body.action}", "provider", pid, before, {"status": p.status, "reason": body.reason})
    notify(db, db.get(User, pid), "provider_status", f"Your application: {p.status}", p.status_reason or "You can now accept jobs.")
    return _prov_row(db, p)


class CommissionIn(BaseModel):
    commission_override_bps: int | None = Field(default=None, ge=0, le=5000)


@router.patch("/providers/{pid}/commission", summary="Set a provider-specific commission (null returns to the default)")
def set_commission(pid: uuid.UUID, body: CommissionIn, request: Request, db: DB, actor: User = perm("payouts.manage")):
    p = db.get(ProviderProfile, pid)
    if p is None:
        raise NotFound("Provider not found.")
    before = {"commission_override_bps": p.commission_override_bps}
    p.commission_override_bps = body.commission_override_bps
    audit(db, request, actor, "provider.commission_changed", "provider", pid, before, body.model_dump())
    return {"commission_override_bps": p.commission_override_bps}


# ---------- bookings ----------
@router.get("/bookings")
def bookings(db: DB, p: Pagination, actor: User = perm("bookings.read"), status: str | None = None, q: str | None = None, unassigned: bool = False):
    stmt = select(Booking).order_by(Booking.starts_at.desc())
    if status:
        stmt = stmt.where(Booking.status == status)
    if unassigned:
        stmt = stmt.where(Booking.provider_id.is_(None), Booking.status.in_(("awaiting_provider", "confirmed")))
    if q:
        stmt = stmt.where(Booking.reference.ilike(f"%{q}%"))
    return paginate(db, stmt, p, lambda b: booking_out(db, b, "admin"))


@router.get("/bookings/{bid}")
def booking_detail(bid: uuid.UUID, db: DB, actor: User = perm("bookings.read")):
    b = db.get(Booking, bid)
    if b is None:
        raise NotFound("Booking not found.")
    out = booking_out(db, b, "admin")
    fin = db.get(finance.BookingFinancial, b.id)
    out["financials"] = None if fin is None else {
        "gross_paid_pence": fin.gross_paid_pence, "service_value_pence": fin.service_value_pence, "commission_pence": fin.commission_pence,
        "fee_pence": fin.fee_pence, "promo_cost_pence": fin.promo_cost_pence, "provider_earning_pence": fin.provider_earning_pence,
        "processing_fee_pence": fin.processing_fee_pence, "processing_fee_source": fin.processing_fee_source, "refunded_pence": fin.refunded_pence,
    }
    return out


@router.get("/bookings/{bid}/candidates", summary="Professionals who could take this booking")
def candidates(bid: uuid.UUID, db: DB, actor: User = perm("bookings.manage")):
    b = db.get(Booking, bid)
    if b is None:
        raise NotFound("Booking not found.")
    from app.models.catalogue import ServiceOffering

    o = db.get(ServiceOffering, b.offering_id)
    cands = rank_candidates(db, o, b.outward_code, b.starts_at, int((b.ends_at - b.starts_at).total_seconds() // 60))
    return [{"id": str(c.user_id), "display_name": c.display_name, "rating_avg": float(c.rating_avg), "jobs_completed": c.jobs_completed} for c in cands]


class AssignIn(BaseModel):
    provider_id: uuid.UUID


@router.post("/bookings/{bid}/assign")
def assign(bid: uuid.UUID, body: AssignIn, request: Request, db: DB, actor: User = perm("bookings.manage")):
    b = db.scalar(select(Booking).where(Booking.id == bid).with_for_update())
    if b is None:
        raise NotFound("Booking not found.")
    before = {"provider_id": str(b.provider_id) if b.provider_id else None}
    svc.admin_assign(db, b, body.provider_id, actor)
    audit(db, request, actor, "booking.assigned", "booking", b.id, before, {"provider_id": str(body.provider_id)})
    return booking_out(db, b, "admin")


class AdminCancelIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


@router.post("/bookings/{bid}/cancel", summary="Cancel on the customer's behalf with a full refund")
def admin_cancel(bid: uuid.UUID, body: AdminCancelIn, request: Request, db: DB, actor: User = perm("bookings.manage", "refunds.manage")):
    b = db.scalar(select(Booking).where(Booking.id == bid).with_for_update())
    if b is None:
        raise NotFound("Booking not found.")
    res = svc.cancel_booking(db, b, actor, "admin", body.reason)
    audit(db, request, actor, "booking.cancelled_by_admin", "booking", b.id, None, {"reason": body.reason, **res})
    return {**res, "booking": booking_out(db, b, "admin")}


class RefundIn(BaseModel):
    amount_pence: int = Field(gt=0)
    reason: str = Field(pattern="^(complaint|goodwill|other)$")
    funded_by: str = Field(default="platform", pattern="^(platform|provider)$")
    note: str = Field(min_length=3, max_length=300)


@router.post("/bookings/{bid}/refund")
def refund(bid: uuid.UUID, body: RefundIn, request: Request, db: DB, actor: User = perm("refunds.manage")):
    b = db.scalar(select(Booking).where(Booking.id == bid).with_for_update())
    if b is None:
        raise NotFound("Booking not found.")
    r = finance.issue_refund(db, b, body.amount_pence, reason=body.reason, funded_by=body.funded_by, actor_id=actor.id)
    audit(db, request, actor, "refund.issued", "booking", b.id, None, body.model_dump())
    notify(db, db.get(User, b.customer_id), "refund_issued", f"Refund for {b.reference}", f"£{body.amount_pence / 100:.2f} has been refunded.", ("in_app", "email"))
    return {"refund_id": str(r.id) if r else None}


# ---------- complaints, refund requests, tickets ----------
@router.get("/complaints")
def complaints(db: DB, p: Pagination, actor: User = perm("complaints.manage"), status: str | None = None):
    stmt = select(Complaint).order_by(Complaint.created_at.desc())
    if status:
        stmt = stmt.where(Complaint.status == status)

    def conv(c: Complaint):
        b = db.get(Booking, c.booking_id)
        return {"id": str(c.id), "reference": str(c.id)[:8].upper(), "booking_id": str(c.booking_id), "booking_reference": b.reference, "category": c.category,
                "severity": c.severity, "description": c.description, "status": c.status, "resolution": c.resolution, "created_at": c.created_at,
                "customer": db.get(User, c.customer_id).full_name, "provider_id": str(c.provider_id) if c.provider_id else None,
                "provider": db.get(ProviderProfile, c.provider_id).display_name if c.provider_id else None}

    return paginate(db, stmt, p, conv)


class ComplaintDecisionIn(BaseModel):
    status: str = Field(pattern="^(investigating|resolved|rejected)$")
    resolution: str | None = Field(default=None, max_length=1000)
    refund_pence: int | None = Field(default=None, ge=1)
    refund_funded_by: str = Field(default="platform", pattern="^(platform|provider)$")


@router.post("/complaints/{cid}/decision")
def decide_complaint(cid: uuid.UUID, body: ComplaintDecisionIn, request: Request, db: DB, actor: User = perm("complaints.manage")):
    c = db.get(Complaint, cid)
    if c is None:
        raise NotFound("Complaint not found.")
    if body.status in ("resolved", "rejected") and not body.resolution:
        raise Unprocessable("Please record the outcome so the customer can be told.", code="resolution_required")
    c.first_response_at = c.first_response_at or utcnow()
    before = {"status": c.status}
    if body.refund_pence:
        if "refunds.manage" not in user_permissions(db, actor):
            raise Forbidden("You do not have permission to issue refunds.")
        b = db.scalar(select(Booking).where(Booking.id == c.booking_id).with_for_update())
        finance.issue_refund(db, b, body.refund_pence, reason="complaint", funded_by=body.refund_funded_by, actor_id=actor.id)
    c.status, c.resolution = body.status, body.resolution
    if body.status in ("resolved", "rejected"):
        c.resolved_by, c.resolved_at = actor.id, utcnow()
    audit(db, request, actor, "complaint.updated", "complaint", c.id, before, body.model_dump())
    notify(db, db.get(User, c.customer_id), "complaint_update", f"Update on your complaint {str(c.id)[:8].upper()}", body.resolution or "We are looking into this.")
    return {"id": str(c.id), "status": c.status}


@router.get("/refund-requests")
def refund_requests(db: DB, p: Pagination, actor: User = perm("refunds.manage"), status: str | None = "open"):
    stmt = select(RefundRequest).order_by(RefundRequest.created_at.desc())
    if status:
        stmt = stmt.where(RefundRequest.status == status)

    def conv(r: RefundRequest):
        b = db.get(Booking, r.booking_id)
        return {"id": str(r.id), "booking_id": str(b.id), "booking_reference": b.reference, "total_pence": b.total_pence, "requested_pence": r.requested_pence,
                "reason": r.reason, "status": r.status, "customer": db.get(User, r.customer_id).full_name, "created_at": r.created_at, "decision_note": r.decision_note}

    return paginate(db, stmt, p, conv)


class RefundDecisionIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    approved_pence: int | None = Field(default=None, ge=1)
    funded_by: str = Field(default="platform", pattern="^(platform|provider)$")
    note: str = Field(min_length=3, max_length=500)


@router.post("/refund-requests/{rid}/decision")
def decide_refund(rid: uuid.UUID, body: RefundDecisionIn, request: Request, db: DB, actor: User = perm("refunds.manage")):
    r = db.get(RefundRequest, rid)
    if r is None:
        raise NotFound("Refund request not found.")
    if r.status != "open":
        raise Conflict("This request has already been decided.", code="already_decided")
    b = db.scalar(select(Booking).where(Booking.id == r.booking_id).with_for_update())
    if body.decision == "approve":
        amount = body.approved_pence or r.requested_pence or b.total_pence
        finance.issue_refund(db, b, amount, reason="complaint", funded_by=body.funded_by, actor_id=actor.id, key=f"rr:{r.id}")
        r.approved_pence = amount
    r.status = "approved" if body.decision == "approve" else "rejected"
    r.decision_note, r.decided_by, r.decided_at = body.note, actor.id, utcnow()
    audit(db, request, actor, "refund_request.decided", "refund_request", r.id, None, body.model_dump())
    notify(db, db.get(User, r.customer_id), "refund_decision", f"Your refund request for {b.reference}", f"Decision: {r.status}. {body.note}")
    return {"id": str(r.id), "status": r.status, "approved_pence": r.approved_pence}


@router.get("/tickets")
def tickets(db: DB, p: Pagination, actor: User = perm("complaints.manage"), status: str | None = None):
    stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc())
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    return paginate(db, stmt, p, lambda t: {"id": str(t.id), "reference": str(t.id)[:8].upper(), "kind": t.kind, "subject": t.subject, "body": t.body, "status": t.status,
                                            "contact": t.contact_email, "response": t.response, "created_at": t.created_at})


class TicketReplyIn(BaseModel):
    response: str = Field(min_length=3, max_length=3000)
    close: bool = True


@router.post("/tickets/{tid}/reply")
def reply_ticket(tid: uuid.UUID, body: TicketReplyIn, request: Request, db: DB, actor: User = perm("complaints.manage")):
    t = db.get(SupportTicket, tid)
    if t is None:
        raise NotFound("Ticket not found.")
    t.response, t.status, t.handled_by = body.response, "closed" if body.close else "in_progress", actor.id
    if t.user_id:
        notify(db, db.get(User, t.user_id), "ticket_reply", f"Reply to: {t.subject}", body.response)
    audit(db, request, actor, "ticket.replied", "support_ticket", t.id)
    return {"id": str(t.id), "status": t.status}


# ---------- payouts ----------
@router.get("/payouts")
def payouts(db: DB, p: Pagination, actor: User = perm("payouts.read"), status: str | None = None):
    stmt = select(Payout).order_by(Payout.release_at.desc())
    if status:
        stmt = stmt.where(Payout.status == status)

    def conv(po: Payout):
        b = db.get(Booking, po.booking_id)
        return {"id": str(po.id), "provider": db.get(ProviderProfile, po.provider_id).display_name, "booking_reference": b.reference, "gross_pence": po.gross_pence,
                "commission_pence": po.commission_pence, "amount_pence": po.amount_pence, "status": po.status, "release_at": po.release_at, "paid_at": po.paid_at, "note": po.note}

    return paginate(db, stmt, p, conv)


@router.get("/adjustments", summary="Amounts professionals owe us, netted off their next payouts")
def adjustments(db: DB, actor: User = perm("payouts.read")):
    from app.models.finance import ProviderAdjustment

    rows = db.scalars(select(ProviderAdjustment).order_by(ProviderAdjustment.created_at.desc()).limit(100)).all()
    return [{"id": str(a.id), "provider": db.get(ProviderProfile, a.provider_id).display_name, "owed_pence": a.owed_pence, "remaining_pence": a.remaining_pence, "note": a.note, "created_at": a.created_at} for a in rows]


class PayoutActionIn(BaseModel):
    action: str = Field(pattern="^(hold|release)$")
    note: str = Field(min_length=3, max_length=200)


@router.post("/payouts/{pid}/action")
def payout_action(pid: uuid.UUID, body: PayoutActionIn, request: Request, db: DB, actor: User = perm("payouts.manage")):
    po = db.get(Payout, pid)
    if po is None:
        raise NotFound("Payout not found.")
    if po.status == "paid":
        raise Conflict("This payout has already been paid.", code="already_paid")
    before = {"status": po.status}
    if body.action == "hold":
        po.status, po.note = "held", body.note
    else:
        po.status, po.release_at, po.note = "pending", utcnow(), body.note
        finance.release_due_payouts(db)
    audit(db, request, actor, f"payout.{body.action}", "payout", po.id, before, {"status": po.status, "note": body.note})
    return {"id": str(po.id), "status": po.status}
