"""Seed reference data (idempotent). Demo accounts are created only when SEED_DEMO=1 and SEED_ADMIN_PASSWORD is set.

Prices, commission and areas are launch assumptions for founder review, not market findings."""
import os
from datetime import date, time, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal, utcnow
from app.core.permissions import PERMISSIONS, ROLES
from app.models.catalogue import (
    Bundle, CategoryRequirement, FrequencyDiscount, OfferingAddon, PriceTier, ServiceArea, ServiceCategory, ServiceOffering,
)
from app.models.engagement import Promotion
from app.models.identity import Permission, Role, RolePermission, User
from app.models.providers import AvailabilityRule, ProviderArea, ProviderDocument, ProviderProfile, ProviderService
from app.services import accounts
from app.services.config_store import ensure_defaults

AREAS = {"SW4": "Clapham", "SW11": "Battersea", "SW12": "Balham", "SW15": "Putney", "SW17": "Tooting", "SW18": "Wandsworth", "SW19": "Wimbledon"}

COMING_SOON = [
    ("handyman", "Handyman", "Small repairs, assembly and fixing."),
    ("gardening", "Gardening", "Lawn care, tidying and seasonal work."),
    ("plumbing", "Plumbing", "Leaks, taps and drainage."),
    ("electrical", "Electrical", "Sockets, lighting and testing."),
    ("gas-heating", "Boiler and heating", "Servicing and repairs."),
]


def seed_rbac(db: Session) -> None:
    perms = {p.key: p for p in db.scalars(select(Permission))}
    for k, d in PERMISSIONS.items():
        if k not in perms:
            perms[k] = Permission(key=k, description=d)
            db.add(perms[k])
    db.flush()
    for key, (desc, staff, plist) in ROLES.items():
        r = db.scalar(select(Role).where(Role.key == key))
        if r is None:
            r = Role(key=key, description=desc, is_staff=staff)
            db.add(r)
            db.flush()
        have = {rp.permission_id for rp in db.scalars(select(RolePermission).where(RolePermission.role_id == r.id))}
        for pk in plist:
            if perms[pk].id not in have:
                db.add(RolePermission(role_id=r.id, permission_id=perms[pk].id))
    db.flush()


def seed_catalogue(db: Session) -> None:
    for code, name in AREAS.items():
        if not db.get(ServiceArea, code):
            db.add(ServiceArea(outward_code=code, name=name))
    if db.scalar(select(ServiceCategory).where(ServiceCategory.slug == "home-cleaning")):
        return
    cat = ServiceCategory(
        slug="home-cleaning", name="Home cleaning", is_active=True, sort_order=1,
        summary="Regular cleaning with a professional you can request by name, and end-of-tenancy cleans for moving day.",
        description="Cleaning is not a regulated trade, so we focus on identity, right to work and insurance documents. Each document is checked by our team before a professional can take bookings.",
    )
    cat.requirements = [
        CategoryRequirement(document_type="identity", is_mandatory=True),
        CategoryRequirement(document_type="right_to_work", is_mandatory=True),
        CategoryRequirement(document_type="public_liability", is_mandatory=True),
        CategoryRequirement(document_type="dbs", is_mandatory=False),
    ]
    db.add(cat)
    db.flush()
    regular = ServiceOffering(
        category_id=cat.id, slug="regular-cleaning", name="Regular home cleaning", pricing_model="hourly", hourly_rate_pence=2200,
        min_minutes=120, max_minutes=480, step_minutes=30, buffer_minutes=30, supports_recurring=True,
        summary="A tidy, clean home on your schedule, from the same professional each visit.",
        description="Choose the number of hours that suits your home. Your professional brings the agreed tasks and works through them in a sensible order. You can ask for the same person every time.",
        included=["Dusting and wiping surfaces", "Vacuuming and mopping floors", "Kitchen worktops, hob and sink", "Bathrooms, toilet and mirrors", "Emptying bins"],
        excluded=["Inside ovens, fridges and windows unless added", "Heavy lifting or moving furniture", "Biohazard or hoarding clean-ups", "Anything at height needing a ladder"],
    )
    regular.addons = [
        OfferingAddon(code="oven", name="Inside the oven", price_pence=2500, extra_minutes=45),
        OfferingAddon(code="fridge", name="Inside the fridge", price_pence=1500, extra_minutes=30),
        OfferingAddon(code="windows", name="Interior windows", price_pence=2000, extra_minutes=45),
        OfferingAddon(code="ironing", name="Ironing (one hour)", price_pence=1200, extra_minutes=60),
    ]
    eot = ServiceOffering(
        category_id=cat.id, slug="end-of-tenancy-cleaning", name="End of tenancy cleaning", pricing_model="tiered", min_minutes=120, max_minutes=720,
        step_minutes=30, buffer_minutes=30, supports_recurring=False,
        summary="A deep, checklist-led clean for handover day, priced by property size.",
        description="A fixed price by number of bedrooms. If your agent or landlord raises a cleaning issue within 48 hours of handover, tell us and we will arrange a re-clean of the items raised.",
        included=["Full kitchen clean including inside the oven", "Bathrooms descaled and sanitised", "Skirting boards, doors and switches wiped", "Floors vacuumed and mopped", "Inside cupboards and wardrobes wiped"],
        excluded=["Carpet shampooing unless added", "Exterior windows", "Rubbish removal", "Pest or damp treatment"],
    )
    eot.tiers = [
        PriceTier(bedrooms=0, label="Studio", price_pence=15000, duration_minutes=240),
        PriceTier(bedrooms=1, label="1 bedroom", price_pence=19000, duration_minutes=300),
        PriceTier(bedrooms=2, label="2 bedrooms", price_pence=25000, duration_minutes=360),
        PriceTier(bedrooms=3, label="3 bedrooms", price_pence=32000, duration_minutes=420),
        PriceTier(bedrooms=4, label="4 bedrooms", price_pence=40000, duration_minutes=480),
    ]
    eot.addons = [
        OfferingAddon(code="carpets", name="Carpet steam clean", price_pence=6000, extra_minutes=60),
        OfferingAddon(code="balcony", name="Balcony or patio", price_pence=2000, extra_minutes=30),
    ]
    db.add_all([regular, eot])
    db.flush()
    db.add_all([
        FrequencyDiscount(offering_id=regular.id, frequency="weekly", percent_bps=1000),
        FrequencyDiscount(offering_id=regular.id, frequency="fortnightly", percent_bps=500),
    ])
    for i, (slug, name, summary) in enumerate(COMING_SOON, start=10):
        db.add(ServiceCategory(slug=slug, name=name, summary=summary, is_active=False, requires_compliance_review=True, sort_order=i,
                               description="Not yet available. Verification requirements for this trade must be defined and reviewed before we open it."))


def seed_bundles(db: Session) -> None:
    """Idempotent, and independent of seed_catalogue so that upgrades add new reference data to existing installations."""
    offerings = {o.slug: o for o in db.scalars(select(ServiceOffering))}
    wanted = [
        ("deep-clean-refresh", "Deep-clean refresh", "Regular clean plus oven, fridge and interior windows.", "regular-cleaning", ["oven", "fridge", "windows"], 1000),
        ("move-out-pack", "Move-out pack", "End of tenancy clean with carpets and balcony.", "end-of-tenancy-cleaning", ["carpets", "balcony"], 1000),
    ]
    have = {b for b in db.scalars(select(Bundle.slug))}
    for slug, name, desc, off, addons, bps in wanted:
        if slug not in have and off in offerings:
            db.add(Bundle(slug=slug, name=name, description=desc, offering_id=offerings[off].id, addon_codes=addons, discount_bps=bps))
    db.flush()


def seed_demo(db: Session, password: str) -> None:
    if db.scalar(select(User.id).where(User.email == "admin@roanwick.example")):
        return
    for email, name, role in [("admin@roanwick.example", "Alex Admin", "super_admin"), ("ops@roanwick.example", "Olivia Operations", "operations"),
                              ("finance@roanwick.example", "Farid Finance", "finance"), ("support@roanwick.example", "Sana Support", "support")]:
        u = accounts.create_user(db, email=email, password=password, full_name=name, phone=None, role=role)
        u.email_verified_at = utcnow()
    c = accounts.create_customer(db, email="priya@example.com", password=password, full_name="Priya Shah", phone="07700900123", referral_code=None, source="direct")
    c.email_verified_at = utcnow()
    offerings = list(db.scalars(select(ServiceOffering)))
    demo_pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    storage = Path(get_settings().storage_dir) / "demo"
    storage.mkdir(parents=True, exist_ok=True)
    (storage / "sample.pdf").write_bytes(demo_pdf)
    people = [("elena@example.com", "Elena Kowalska", "Elena K.", ["SW11", "SW12", "SW18"]), ("tomasz@example.com", "Tomasz Nowak", "Tomasz N.", ["SW4", "SW12", "SW17"]),
              ("amara@example.com", "Amara Okafor", "Amara O.", ["SW15", "SW18", "SW19"])]
    for email, full, display, areas in people:
        u = accounts.create_user(db, email=email, password=password, full_name=full, phone="07700900456", role="provider")
        u.email_verified_at = utcnow()
        p = ProviderProfile(user_id=u.id, display_name=display, bio=f"{display} has been cleaning homes across south-west London. Reliable, tidy and happy to build a regular routine.", years_experience=6,
                            languages=["English"], status="approved", approved_at=utcnow())
        p.services = [ProviderService(provider_id=u.id, offering_id=o.id) for o in offerings]
        p.areas = [ProviderArea(provider_id=u.id, outward_code=a) for a in areas]
        db.add(p)
        db.flush()
        for wd in range(5):
            db.add(AvailabilityRule(provider_id=u.id, weekday=wd, start_time=time(8, 0), end_time=time(18, 0)))
        db.add(AvailabilityRule(provider_id=u.id, weekday=5, start_time=time(9, 0), end_time=time(15, 0)))
        for t, title in (("identity", "Passport"), ("right_to_work", "Share code check"), ("public_liability", "Public liability certificate")):
            db.add(ProviderDocument(provider_id=u.id, doc_type=t, title=title, storage_key="demo/sample.pdf", original_name="sample.pdf", content_type="application/pdf", size_bytes=len(demo_pdf),
                                    status="approved", expires_on=date.today() + timedelta(days=365) if t == "public_liability" else None, reviewed_at=utcnow(), review_notes="Demo data"))
    db.add(Promotion(code="WELCOME10", description="10% off your first booking", kind="percent", value=1000, first_booking_only=True, max_discount_pence=1500, per_user_limit=1, channel="welcome"))
    db.add(Promotion(code="SPRING5", description="£5 off bookings over £60", kind="fixed", value=500, min_spend_pence=6000, per_user_limit=1, channel="seasonal"))


def run() -> None:
    with SessionLocal() as db:
        seed_rbac(db)
        ensure_defaults(db)
        seed_catalogue(db)
        seed_bundles(db)
        if os.environ.get("SEED_DEMO") == "1":
            pw = get_settings().seed_admin_password
            if len(pw) < 10:
                raise SystemExit("Set SEED_ADMIN_PASSWORD (10+ characters) to seed demo accounts.")
            seed_demo(db, pw)
        db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    run()
