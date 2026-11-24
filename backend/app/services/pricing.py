"""Itemised quotations. All amounts are integer pence."""
import uuid
from datetime import timedelta
from math import ceil

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import NotFound, Unprocessable
from app.models.catalogue import Bundle, FrequencyDiscount, Quotation, QuotationLine, ServiceArea, ServiceOffering
from app.models.bookings import Booking
from app.models.engagement import Promotion, PromotionRedemption
from app.models.identity import User
from app.services.config_store import get_setting
from app.services.postcodes import normalise_postcode


def _refund_phrase(bps: int) -> str:
    return "full refund" if bps >= 10000 else "no refund" if bps <= 0 else f"{bps / 100:g}% refunded"


def cancellation_terms(db: Session) -> dict:
    tiers = sorted(get_setting(db, "cancellation_tiers"), key=lambda t: -t["hours_before"])
    lines = []
    for i, t in enumerate(tiers):
        lower = tiers[i + 1]["hours_before"] if i + 1 < len(tiers) else None
        if i == 0:
            when = f"More than {t['hours_before']} hours before the start"
        elif t["hours_before"] == 0 and lower is None:
            when = f"Less than {tiers[i - 1]['hours_before']} hours before the start"
        else:
            when = f"Between {t['hours_before']} and {tiers[i - 1]['hours_before']} hours before the start"
        lines.append(f"{when}: {_refund_phrase(t['refund_bps'])}.")
    return {
        "tiers": tiers,
        "summary": lines,
        "provider_cancellation": "If your professional cancels, you receive a full refund and we will try to find a replacement.",
    }


def refund_bps_for(db: Session, hours_before: float) -> int:
    for t in sorted(get_setting(db, "cancellation_tiers"), key=lambda t: -t["hours_before"]):
        if hours_before > t["hours_before"] or (t["hours_before"] == 0):
            return t["refund_bps"]
    return 0


def validate_promo(db: Session, code: str, user: User | None, eligible_pence: int) -> tuple[Promotion, int]:
    promo = db.scalar(select(Promotion).where(Promotion.code == code.strip().upper()))
    today = utcnow().date()
    if promo is None or not promo.is_active:
        raise Unprocessable("That promotional code is not valid.", code="promo_invalid")
    if (promo.valid_from and today < promo.valid_from) or (promo.valid_to and today > promo.valid_to):
        raise Unprocessable("That promotional code has expired.", code="promo_expired")
    if promo.max_redemptions is not None and promo.redemption_count >= promo.max_redemptions:
        raise Unprocessable("That promotional code has been fully redeemed.", code="promo_exhausted")
    if eligible_pence < promo.min_spend_pence:
        raise Unprocessable(
            f"This code needs a minimum spend of £{promo.min_spend_pence / 100:.2f}.", code="promo_min_spend"
        )
    if user is not None:
        used = db.query(PromotionRedemption).filter_by(promotion_id=promo.id, user_id=user.id).count()
        if used >= promo.per_user_limit:
            raise Unprocessable("You have already used this code.", code="promo_used")
        if promo.first_booking_only:
            prior = db.query(Booking).filter(Booking.customer_id == user.id, Booking.status.in_(["confirmed", "in_progress", "completed", "awaiting_provider"])).count()
            if prior:
                raise Unprocessable("This code is for first bookings only.", code="promo_first_only")
    discount = ceil(eligible_pence * promo.value / 10000) if promo.kind == "percent" else promo.value
    if promo.max_discount_pence is not None:
        discount = min(discount, promo.max_discount_pence)
    return promo, min(discount, eligible_pence)


def build_quote(
    db: Session,
    *,
    user: User | None,
    offering_id: uuid.UUID,
    postcode: str,
    minutes: int | None = None,
    bedrooms: int | None = None,
    addon_codes: list[str] | None = None,
    frequency: str = "once",
    promo_code: str | None = None,
    bundle_slug: str | None = None,
) -> Quotation:
    offering = db.get(ServiceOffering, offering_id)
    if offering is None or not offering.is_active or not offering.category.is_active:
        raise NotFound("That service is not available.")
    formatted, outward = normalise_postcode(postcode)
    area = db.get(ServiceArea, outward)
    if area is None or not area.is_active:
        raise Unprocessable(
            f"We do not cover {outward} yet. Leave your email and we will tell you when we do.", code="outside_coverage"
        )
    if frequency not in ("once", "weekly", "fortnightly"):
        raise Unprocessable("Frequency must be once, weekly or fortnightly.")
    if frequency != "once" and not offering.supports_recurring:
        raise Unprocessable("This service cannot be booked on a recurring basis.")

    lines: list[tuple[str, str, int]] = []
    if offering.pricing_model == "hourly":
        m = minutes or offering.min_minutes
        if m % offering.step_minutes or m < offering.min_minutes or m > offering.max_minutes:
            raise Unprocessable(
                f"Choose between {offering.min_minutes // 60} and {offering.max_minutes // 60} hours in {offering.step_minutes}-minute steps."
            )
        labour = round(offering.hourly_rate_pence * m / 60)
        duration = m
        whole, part = divmod(m, 60)
        length = f"{whole} hour{'' if whole == 1 else 's'}" + (f" {part} minutes" if part else "")
        lines.append(("labour", f"Cleaning, {length} at £{offering.hourly_rate_pence / 100:.2f}/hour", labour))
    else:
        tier = next((t for t in offering.tiers if t.bedrooms == bedrooms), None)
        if tier is None:
            raise Unprocessable("Please choose a property size.", code="size_required")
        duration = tier.duration_minutes
        lines.append(("labour", f"{offering.name}, {tier.label}", tier.price_pence))

    bundle = None
    if bundle_slug:
        bundle = db.scalar(select(Bundle).where(Bundle.slug == bundle_slug, Bundle.is_active.is_(True)))
        if bundle is None or bundle.offering_id != offering.id:
            raise Unprocessable("That bundle is not available for this service.", code="bundle_invalid")
        addon_codes = list(dict.fromkeys([*bundle.addon_codes, *(addon_codes or [])]))
    chosen = {a.code: a for a in offering.addons if a.is_active}
    for code in addon_codes or []:
        a = chosen.get(code)
        if a is None:
            raise Unprocessable(f"Unknown extra: {code}.")
        lines.append(("addon", a.name, a.price_pence))
        duration += a.extra_minutes

    discount_total = 0
    if frequency != "once":
        fd = db.scalar(select(FrequencyDiscount).where(FrequencyDiscount.offering_id == offering.id, FrequencyDiscount.frequency == frequency))
        if fd:
            labour_amt = lines[0][2]
            d = round(labour_amt * fd.percent_bps / 10000)
            lines.append(("discount", f"{frequency.capitalize()} plan discount ({fd.percent_bps // 100}% off labour)", -d))
            discount_total += d
    if bundle and bundle.discount_bps:
        base = sum(a for k, _, a in lines if k in ("labour", "addon"))
        d = round(base * bundle.discount_bps / 10000)
        lines.append(("bundle", f"{bundle.name} bundle ({bundle.discount_bps / 100:g}% off)", -d))
        discount_total += d
    eligible = sum(a for _, _, a in lines)

    promo_code_used = None
    if promo_code:
        promo, pd = validate_promo(db, promo_code, user, eligible)
        lines.append(("promo", f"Code {promo.code}: {promo.description or 'promotional discount'}", -pd))
        discount_total += pd
        promo_code_used = promo.code

    fee = int(get_setting(db, "customer_booking_fee_pence"))
    if fee:
        lines.append(("fee", "Booking fee", fee))

    subtotal = sum(a for k, _, a in lines if k in ("labour", "addon"))
    total = sum(a for _, _, a in lines)
    q = Quotation(
        user_id=user.id if user else None,
        offering_id=offering.id,
        postcode=formatted,
        outward_code=outward,
        inputs={"minutes": minutes, "bedrooms": bedrooms, "addons": addon_codes or [], "frequency": frequency, "bundle": bundle_slug},
        duration_minutes=duration,
        subtotal_pence=subtotal,
        discount_pence=discount_total,
        fee_pence=fee,
        total_pence=total,
        promo_code=promo_code_used,
        expires_at=utcnow() + timedelta(minutes=int(get_setting(db, "quote_valid_minutes"))),
        terms=cancellation_terms(db),
    )
    for i, (kind, desc, amt) in enumerate(lines):
        q.lines.append(QuotationLine(position=i, kind=kind, description=desc, amount_pence=amt))
    db.add(q)
    db.flush()
    return q
