import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.update(
    ENV="test",
    DATABASE_URL=os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://roanwick:roanwick_dev@localhost:5432/roanwick_test"),
    JWT_SECRET="test-secret-test-secret-test-secret-0123",
    STORAGE_DIR=tempfile.mkdtemp(prefix="rw-test-"),
    PAYMENT_PROVIDER="sandbox",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
LONDON = ZoneInfo("Europe/London")
PASSWORD = "Correct-horse-9"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    with engine.begin() as c:
        c.execute(text("drop schema public cascade"))
        c.execute(text("create schema public"))
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, capture_output=True, text=True, env=os.environ)
    assert r.returncode == 0, r.stderr
    from app import seed

    with SessionLocal() as db:
        seed.seed_rbac(db)
        seed.seed_catalogue(db)
        seed.seed_bundles(db)
        db.commit()
    yield


TRANSACTIONAL = (
    "users, promotions, audit_events, metric_events, webhook_events, idempotency_records, business_costs, notifications, app_settings, feature_flags"
)


@pytest.fixture(autouse=True)
def _clean():
    from app.services.config_store import ensure_defaults

    with engine.begin() as c:
        c.execute(text(f"truncate {TRANSACTIONAL} cascade"))
        # Reference data that individual tests are allowed to change is put back.
        c.execute(text("delete from price_tiers where offering_id in (select id from service_offerings where slug = 'lawn')"))
        c.execute(text("delete from service_offerings where slug = 'lawn'"))
        c.execute(text("delete from bundles where slug not in ('deep-clean-refresh', 'move-out-pack')"))
        c.execute(text("update service_categories set is_active = (slug = 'home-cleaning')"))
        c.execute(text("delete from category_requirements where category_id in (select id from service_categories where slug <> 'home-cleaning')"))
    with SessionLocal() as db:
        ensure_defaults(db)
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


def slot(days_ahead: int = 4, hour: int = 10, minute: int = 0, weekday: int | None = None) -> datetime:
    """A London-local start time at least `days_ahead` days away, optionally forced onto a weekday (0 = Monday)."""
    d = date.today() + timedelta(days=days_ahead)
    while weekday is not None and d.weekday() != weekday:
        d += timedelta(days=1)
    return datetime.combine(d, time(hour, minute), tzinfo=LONDON)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_customer(client, email="priya@example.com", **extra) -> dict:
    r = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "full_name": "Priya Shah", "accept_terms": True, **extra})
    assert r.status_code == 201, r.text
    return {"token": r.json()["access_token"], "headers": auth(r.json()["access_token"]), "id": r.json()["user"]["id"], "email": email}


def make_staff(role="super_admin", email="admin@roanwick.example"):
    from app.services import accounts

    with SessionLocal() as db:
        accounts.create_user(db, email=email, password=PASSWORD, full_name="Staff Member", phone=None, role=role)
        db.commit()


def login(client, email, password=PASSWORD) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return auth(r.json()["access_token"])


def make_provider(client, email="elena@example.com", areas=("SW11", "SW12"), approved=True, auto_accept=True, hours=((0, 8, 18), (1, 8, 18), (2, 8, 18), (3, 8, 18), (4, 8, 18), (5, 9, 15)),
                  insurance_days=365, name="Elena K."):
    """Create a provider directly in the database, bypassing onboarding, for tests of other flows."""
    from app.models.catalogue import ServiceOffering
    from app.models.providers import AvailabilityRule, ProviderArea, ProviderDocument, ProviderProfile, ProviderService
    from app.services import accounts
    from app.core.db import utcnow
    from sqlalchemy import select

    with SessionLocal() as s:
        u = accounts.create_user(s, email=email, password=PASSWORD, full_name=name, phone="07700900456", role="provider")
        p = ProviderProfile(user_id=u.id, display_name=name, bio="Experienced and reliable cleaner in south-west London.", status="approved" if approved else "submitted",
                            approved_at=utcnow() if approved else None, auto_accept=auto_accept)
        p.services = [ProviderService(provider_id=u.id, offering_id=o.id) for o in s.scalars(select(ServiceOffering))]
        p.areas = [ProviderArea(provider_id=u.id, outward_code=a) for a in areas]
        s.add(p)
        s.flush()
        for wd, a, b in hours:
            s.add(AvailabilityRule(provider_id=u.id, weekday=wd, start_time=time(a), end_time=time(b)))
        for t in ("identity", "right_to_work", "public_liability"):
            s.add(ProviderDocument(provider_id=u.id, doc_type=t, title=t, storage_key="x.pdf", original_name="x.pdf", content_type="application/pdf", size_bytes=10,
                                   status="approved", expires_on=date.today() + timedelta(days=insurance_days) if t == "public_liability" else None))
        s.commit()
        uid = str(u.id)
    return {"id": uid, "email": email, "headers": login(client, email)}


def offering_id(client, slug="regular-cleaning") -> str:
    return client.get(f"/api/v1/catalogue/offerings/{slug}").json()["id"]


def add_address(client, who, postcode="SW11 1AB", bedrooms=2):
    r = client.post("/api/v1/addresses", headers=who["headers"], json={"line1": "12 Example Road", "postcode": postcode, "bedrooms": bedrooms})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def quote(client, who, postcode="SW11 1AB", minutes=180, **extra):
    r = client.post("/api/v1/quotes", headers=who["headers"] if who else {}, json={"offering_id": offering_id(client), "postcode": postcode, "minutes": minutes, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def book(client, who, starts_at, qid=None, addr=None, provider_id=None, key=None, **extra):
    qid = qid or quote(client, who)["id"]
    addr = addr or add_address(client, who)
    headers = dict(who["headers"])
    if key:
        headers["Idempotency-Key"] = key
    return client.post("/api/v1/bookings", headers=headers, json={"quotation_id": qid, "address_id": addr, "starts_at": starts_at.isoformat(), "provider_id": provider_id, "accept_terms": True, **extra})


def pay(client, who, booking_id, method="pm_card_visa", key=None):
    headers = dict(who["headers"])
    if key:
        headers["Idempotency-Key"] = key
    return client.post(f"/api/v1/bookings/{booking_id}/pay", headers=headers, json={"payment_method": method})


def shift_booking(booking_id, start: datetime):
    """Move a booking in the database (to test time-dependent rules without waiting)."""
    from app.models.bookings import Booking
    import uuid as _u

    with SessionLocal() as s:
        b = s.get(Booking, _u.UUID(booking_id))
        dur = b.ends_at - b.starts_at
        buf = b.blocked_until - b.ends_at
        b.starts_at, b.ends_at, b.blocked_until = start, start + dur, start + dur + buf
        s.commit()


def confirmed_booking(client, who, start=None, **kw):
    start = start or slot(4, 10, weekday=1)
    r = book(client, who, start, **kw)
    assert r.status_code == 201, r.text
    p = pay(client, who, r.json()["id"])
    assert p.status_code == 200, p.text
    return p.json()
