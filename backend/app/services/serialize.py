from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bookings import Booking
from app.models.catalogue import Quotation, ServiceCategory, ServiceOffering
from app.models.engagement import Review
from app.models.identity import User
from app.models.providers import ProviderProfile
from app.services import finance
from app.services.bookings import refund_preview
from app.services.verification import badges


def offering_out(o: ServiceOffering) -> dict:
    return {
        "id": str(o.id), "slug": o.slug, "name": o.name, "summary": o.summary, "description": o.description,
        "included": o.included, "excluded": o.excluded, "pricing_model": o.pricing_model, "hourly_rate_pence": o.hourly_rate_pence,
        "min_minutes": o.min_minutes, "max_minutes": o.max_minutes, "step_minutes": o.step_minutes,
        "supports_recurring": o.supports_recurring, "frequency_discounts": {d.frequency: d.percent_bps for d in o.frequency_discounts}, "category": {"slug": o.category.slug, "name": o.category.name},
        "addons": [{"code": a.code, "name": a.name, "price_pence": a.price_pence, "extra_minutes": a.extra_minutes} for a in o.addons if a.is_active],
        "tiers": sorted(({"bedrooms": t.bedrooms, "label": t.label, "price_pence": t.price_pence, "duration_minutes": t.duration_minutes} for t in o.tiers), key=lambda t: t["bedrooms"]),
    }


def category_out(c: ServiceCategory) -> dict:
    return {
        "slug": c.slug, "name": c.name, "summary": c.summary, "description": c.description, "available": c.is_active,
        "coming_soon": (not c.is_active), "offerings": [offering_out(o) for o in c.offerings if o.is_active] if c.is_active else [],
    }


def quote_out(q: Quotation) -> dict:
    return {
        "id": str(q.id), "offering_id": str(q.offering_id), "postcode": q.postcode, "inputs": q.inputs, "duration_minutes": q.duration_minutes,
        "lines": [{"kind": l.kind, "description": l.description, "amount_pence": l.amount_pence} for l in q.lines],
        "subtotal_pence": q.subtotal_pence, "discount_pence": q.discount_pence, "fee_pence": q.fee_pence, "total_pence": q.total_pence,
        "promo_code": q.promo_code, "expires_at": q.expires_at, "terms": q.terms,
    }


def pro_public(db: Session, p: ProviderProfile, full: bool = False) -> dict:
    out = {
        "id": str(p.user_id), "display_name": p.display_name, "bio": p.bio, "years_experience": p.years_experience,
        "languages": p.languages, "rating_avg": float(p.rating_avg), "rating_count": p.rating_count, "jobs_completed": p.jobs_completed,
        "badges": badges(db, p.user_id),
    }
    if full:
        rows = db.scalars(select(Review).where(Review.provider_id == p.user_id, Review.is_published.is_(True)).order_by(Review.created_at.desc()).limit(10)).all()
        out["reviews"] = [{"rating": r.rating, "comment": r.comment, "reply": r.provider_reply, "at": r.created_at} for r in rows]
    return out


def booking_out(db: Session, b: Booking, viewer: str = "customer") -> dict:
    prov = db.get(ProviderProfile, b.provider_id) if b.provider_id else None
    pay = finance.booking_payment(db, b.id)
    show_address = viewer != "provider" or b.status in ("confirmed", "in_progress", "completed")
    addr = dict(b.address_snapshot)
    if not show_address:
        addr = {"postcode": b.outward_code, "city": addr.get("city")}
    out = {
        "id": str(b.id), "reference": b.reference, "status": b.status, "starts_at": b.starts_at, "ends_at": b.ends_at,
        "offering": {"id": str(b.offering_id), "name": db.get(ServiceOffering, b.offering_id).name, "slug": db.get(ServiceOffering, b.offering_id).slug},
        "address": addr, "customer_notes": b.customer_notes if show_address else None, "total_pence": b.total_pence,
        "lines": [{"kind": l.kind, "description": l.description, "amount_pence": l.amount_pence} for l in b.lines],
        "history": [{"status": h.to_status, "at": h.at, "note": h.note} for h in b.history],
        "terms": b.terms_snapshot, "inputs": b.inputs, "subscription_id": str(b.subscription_id) if b.subscription_id else None,
        "assignment_mode": b.assignment_mode, "hold_expires_at": b.hold_expires_at if b.status == "pending_payment" else None,
        "cancelled_by": b.cancelled_by, "cancel_reason": b.cancel_reason, "created_at": b.created_at,
        "professional": pro_public(db, prov) if prov and viewer != "provider" else None,
    }
    if viewer == "customer":
        out["payment"] = {"status": pay.status, "amount_pence": pay.amount_pence, "credit_applied_pence": pay.credit_applied_pence, "failure_message": pay.failure_message} if pay else None
        if b.status in ("awaiting_provider", "confirmed"):
            out["cancellation_preview"] = refund_preview(db, b)
        out["reviewed"] = db.scalar(select(Review.id).where(Review.booking_id == b.id)) is not None
    else:
        cust = db.get(User, b.customer_id)
        out["customer"] = {"first_name": cust.full_name.split()[0]}
        fin_basis = sum(l.amount_pence for l in b.lines if l.kind in ("labour", "addon", "discount"))
        bps = finance.commission_bps_for(db, prov)
        out["earnings_preview"] = {
            "service_value_pence": fin_basis, "commission_bps": bps, "commission_pence": round(fin_basis * bps / 10000),
            "net_pence": fin_basis - round(fin_basis * bps / 10000),
        }
    if viewer == "admin":
        out["customer"] = {"id": str(b.customer_id), "name": db.get(User, b.customer_id).full_name, "email": db.get(User, b.customer_id).email}
        out["provider_id"] = str(b.provider_id) if b.provider_id else None
    return out
