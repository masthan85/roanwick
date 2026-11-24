import uuid
from datetime import date

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import DB, MaybeUser
from app.core.errors import NotFound
from app.core.ratelimit import limiter
from app.models.catalogue import Bundle, Quotation, ServiceArea, ServiceCategory, ServiceOffering
from app.models.engagement import SupportTicket
from app.models.providers import ProviderProfile
from app.models.system import MetricEvent
from app.services import availability as avail
from app.services import pricing
from app.services.bookings import expire_holds
from app.services.config_store import flag, get_setting
from app.services.postcodes import normalise_postcode
from app.services.serialize import category_out, offering_out, pro_public, quote_out

router = APIRouter(tags=["Public"])


@router.get("/public/config", summary="Customer-facing business configuration")
def public_config(db: DB):
    return {
        "currency": "GBP", "booking_fee_pence": get_setting(db, "customer_booking_fee_pence"),
        "cancellation_terms": pricing.cancellation_terms(db), "prices_include_vat": get_setting(db, "prices_include_vat"),
        "features": {k: flag(db, k) for k in ("recurring_plans", "referrals", "promotions", "customer_chooses_provider", "provider_self_signup")},
        "payment_mode": get_settings().payment_provider,
    }


@router.get("/public/coverage", summary="Is this postcode covered?")
def coverage(db: DB, postcode: str = Query(min_length=5, max_length=10)):
    formatted, outward = normalise_postcode(postcode)
    area = db.get(ServiceArea, outward)
    return {"postcode": formatted, "outward_code": outward, "covered": bool(area and area.is_active), "area_name": area.name if area else None}


@router.get("/public/areas", summary="Postcode districts we currently serve")
def public_areas(db: DB):
    return [{"outward_code": a.outward_code, "name": a.name} for a in db.scalars(select(ServiceArea).where(ServiceArea.is_active.is_(True)).order_by(ServiceArea.outward_code))]


class WaitlistIn(BaseModel):
    email: EmailStr
    postcode: str = Field(min_length=5, max_length=10)


@router.post("/public/waitlist", status_code=202, summary="Join the waiting list for an uncovered area")
@limiter.limit("10/hour")
def waitlist(body: WaitlistIn, db: DB, request: Request):
    _, outward = normalise_postcode(body.postcode)
    db.add(MetricEvent(name="waitlist_signup", props={"email": body.email.lower(), "outward_code": outward}))
    return {"message": "Thank you. We will email you when we reach your area."}


@router.get("/catalogue/categories")
def categories(db: DB):
    cats = db.scalars(select(ServiceCategory).order_by(ServiceCategory.sort_order)).unique().all()
    return [category_out(c) for c in cats]


@router.get("/catalogue/bundles", summary="Priced packages of extras")
def bundles(db: DB, offering: str | None = None):
    stmt = select(Bundle).where(Bundle.is_active.is_(True)).order_by(Bundle.name)
    out = []
    for b in db.scalars(stmt):
        o = db.get(ServiceOffering, b.offering_id)
        if not o.is_active or not o.category.is_active or (offering and o.slug != offering):
            continue
        out.append({"slug": b.slug, "name": b.name, "description": b.description, "offering": o.slug, "addon_codes": b.addon_codes, "discount_bps": b.discount_bps,
                    "addons": [{"code": a.code, "name": a.name} for a in o.addons if a.code in b.addon_codes]})
    return out


@router.get("/catalogue/offerings/{slug}")
def offering(slug: str, db: DB):
    o = db.scalar(select(ServiceOffering).where(ServiceOffering.slug == slug, ServiceOffering.is_active.is_(True)))
    if o is None or not o.category.is_active:
        raise NotFound("Service not found.")
    return offering_out(o)


@router.get("/catalogue/slots", summary="Available start times for a service at a postcode")
def slots(
    db: DB, offering: str, postcode: str, minutes: int | None = None, bedrooms: int | None = None, addons: str = "",
    frequency: str = "once", from_date: date | None = None, days: int = Query(7, ge=1, le=14), provider_id: uuid.UUID | None = None,
):
    expire_holds(db)
    o = db.scalar(select(ServiceOffering).where(ServiceOffering.slug == offering, ServiceOffering.is_active.is_(True)))
    if o is None or not o.category.is_active:
        raise NotFound("Service not found.")
    sp = db.begin_nested()  # the quotation is only used to learn the duration, so it is rolled back
    q = pricing.build_quote(db, user=None, offering_id=o.id, postcode=postcode, minutes=minutes, bedrooms=bedrooms,
                            addon_codes=[a for a in addons.split(",") if a], frequency=frequency)
    duration, outward = q.duration_minutes, q.outward_code
    sp.rollback()
    result = avail.search_slots(db, o, outward, duration, from_date or date.today(), days, provider_id)
    return {"duration_minutes": duration, "days": result}


class QuoteIn(BaseModel):
    offering_id: uuid.UUID
    postcode: str
    minutes: int | None = None
    bedrooms: int | None = Field(default=None, ge=0, le=10)
    addons: list[str] = []
    frequency: str = "once"
    promo_code: str | None = Field(default=None, max_length=30)
    bundle: str | None = Field(default=None, max_length=60)


@router.post("/quotes", status_code=201, summary="Create an itemised quotation")
@limiter.limit("60/minute")
def create_quote(body: QuoteIn, db: DB, user: MaybeUser, request: Request):
    q = pricing.build_quote(db, user=user, offering_id=body.offering_id, postcode=body.postcode, minutes=body.minutes,
                            bedrooms=body.bedrooms, addon_codes=body.addons, frequency=body.frequency, promo_code=body.promo_code, bundle_slug=body.bundle)
    db.add(MetricEvent(name="quote_created", user_id=user.id if user else None, props={"offering": str(body.offering_id), "total": q.total_pence}))
    return quote_out(q)


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: uuid.UUID, db: DB):
    q = db.get(Quotation, quote_id)
    if q is None:
        raise NotFound("Quotation not found.")
    return quote_out(q)


@router.get("/catalogue/professionals", summary="Professionals who can serve a service at a postcode")
def available_professionals(db: DB, offering: str, postcode: str):
    o = db.scalar(select(ServiceOffering).where(ServiceOffering.slug == offering, ServiceOffering.is_active.is_(True)))
    if o is None or not o.category.is_active:
        raise NotFound("Service not found.")
    _, outward = normalise_postcode(postcode)
    pros = avail.eligible_providers(db, o, outward)
    return [pro_public(db, p) for p in sorted(pros, key=lambda p: (-float(p.rating_avg), -p.jobs_completed))]


@router.get("/professionals/{pro_id}", summary="Public professional profile")
def professional(pro_id: uuid.UUID, db: DB):
    p = db.get(ProviderProfile, pro_id)
    if p is None or p.status != "approved":
        raise NotFound("Professional not found.")
    return pro_public(db, p, full=True)


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    subject: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=10, max_length=3000)


@router.post("/contact", status_code=201)
@limiter.limit("5/hour")
def contact(body: ContactIn, db: DB, request: Request):
    t = SupportTicket(contact_email=body.email, subject=body.subject, body=f"From {body.name}: {body.message}", kind="general")
    db.add(t)
    db.flush()
    return {"reference": str(t.id)[:8].upper(), "message": "Thanks. We aim to reply within one working day."}
