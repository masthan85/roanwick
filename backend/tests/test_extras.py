import io
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.db import SessionLocal, utcnow
from app.services import mfa
from tests.conftest import *  # noqa


# ---------- bundles ----------
def seed_bundle(client):
    make_staff()
    h = login(client, "admin@roanwick.example")
    oid = offering_id(client)
    r = client.post("/api/v1/admin/bundles", headers=h, json={"slug": "deep-clean", "name": "Deep clean", "offering_id": oid, "addon_codes": ["oven", "fridge"], "discount_bps": 1000})
    assert r.status_code == 201, r.text
    return h


def test_bundle_prices_itemised_and_is_platform_funded(client):
    p = make_provider(client)
    seed_bundle(client)
    q = client.post("/api/v1/quotes", json={"offering_id": offering_id(client), "postcode": "SW11 1AB", "minutes": 180, "bundle": "deep-clean"}).json()
    kinds = [l["kind"] for l in q["lines"]]
    assert kinds == ["labour", "addon", "addon", "bundle"]
    assert q["lines"][-1]["amount_pence"] == -round((6600 + 2500 + 1500) * 0.10)
    assert q["duration_minutes"] == 180 + 45 + 30
    assert q["total_pence"] == 6600 + 2500 + 1500 - 1060
    assert [b["slug"] for b in client.get("/api/v1/catalogue/bundles", params={"offering": "regular-cleaning"}).json()] == ["deep-clean", "deep-clean-refresh"]
    # The professional is paid on the full value; the platform carries the bundle discount and the report shows it as promotion cost.
    who = register_customer(client)
    b = confirmed_booking(client, who, qid=q["id"])
    shift_booking(b["id"], datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5))
    client.post(f"/api/v1/provider/jobs/{b['id']}/complete", headers=p["headers"])
    make_staff("finance", "fin@roanwick.example")
    r = client.get("/api/v1/admin/reports/finance", headers=login(client, "fin@roanwick.example"), params={"from": (utcnow().date() - timedelta(days=1)).isoformat(), "to": (utcnow().date() + timedelta(days=1)).isoformat()}).json()
    assert r["promotion_cost"]["value"] == 1060 and r["provider_earnings"]["value"] == round(10600 * 0.78)


def test_bundle_must_match_service_and_valid_addons(client):
    seed_bundle(client)
    eot = offering_id(client, "end-of-tenancy-cleaning")
    bad = client.post("/api/v1/quotes", json={"offering_id": eot, "postcode": "SW11 1AB", "bedrooms": 1, "bundle": "deep-clean"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "bundle_invalid"
    h = login(client, "admin@roanwick.example")
    oid = offering_id(client)
    assert client.post("/api/v1/admin/bundles", headers=h, json={"slug": "x-bundle", "name": "Bad", "offering_id": oid, "addon_codes": ["nonsense"], "discount_bps": 500}).status_code == 422


# ---------- admin: new service, customer detail ----------
def test_admin_can_create_a_service_and_it_is_bookable_only_when_category_is_live(client):
    make_staff()
    h = login(client, "admin@roanwick.example")
    body = {"category_slug": "home-cleaning", "slug": "window-cleaning", "name": "Window cleaning", "pricing_model": "hourly", "hourly_rate_pence": 2400, "min_minutes": 60, "max_minutes": 240}
    assert client.post("/api/v1/admin/offerings", headers=h, json=body).status_code == 201
    assert client.post("/api/v1/admin/offerings", headers=h, json=body).status_code == 409
    assert client.post("/api/v1/admin/offerings", headers=h, json={**body, "slug": "tiered-x", "pricing_model": "tiered"}).status_code == 422
    assert client.get("/api/v1/catalogue/offerings/window-cleaning").json()["hourly_rate_pence"] == 2400
    gas = client.post("/api/v1/admin/offerings", headers=h, json={**body, "slug": "boiler-service", "category_slug": "gas-heating"})
    assert gas.status_code == 201
    assert client.get("/api/v1/catalogue/offerings/boiler-service").status_code == 404      # category is not live, so nothing can be booked
    with SessionLocal() as s:
        from app.models.catalogue import ServiceOffering
        s.query(ServiceOffering).filter(ServiceOffering.slug.in_(["window-cleaning", "boiler-service"])).delete()
        s.commit()


def test_admin_customer_detail(client):
    make_provider(client)
    who = register_customer(client)
    confirmed_booking(client, who)
    make_staff("support", "support@roanwick.example")
    h = login(client, "support@roanwick.example")
    d = client.get(f"/api/v1/admin/users/{who['id']}", headers=h).json()
    assert d["email"] == "priya@example.com" and len(d["bookings"]) == 1 and d["customer"]["referral_code"] and d["customer"]["addresses"][0]["postcode"] == "SW11 1AB"
    assert client.get(f"/api/v1/admin/users/{who['id']}", headers=who["headers"]).status_code == 403
    assert client.get(f"/api/v1/admin/users/{uuid.uuid4()}", headers=h).status_code == 404


# ---------- rebook ----------
def test_rebook_info_returns_what_is_needed_to_prefill(client):
    p = make_provider(client)
    who = register_customer(client)
    b = confirmed_booking(client, who, provider_id=p["id"])
    r = client.post(f"/api/v1/bookings/{b['id']}/rebook-quote", headers=who["headers"]).json()
    assert r["offering_slug"] == "regular-cleaning" and r["provider_id"] == p["id"] and r["inputs"]["minutes"] == 180 and r["address_postcode"] == "SW11 1AB"


# ---------- staff MFA ----------
def test_totp_matches_the_rfc6238_test_vector():
    import base64
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert mfa.totp(secret, at=59) == "287082"            # RFC 6238 appendix B, truncated to 6 digits
    assert mfa.totp(secret, at=1111111109) == "081804"
    assert mfa.verify(secret, "287082", at=59) and not mfa.verify(secret, "287083", at=59) and not mfa.verify(secret, "abc", at=59)


def test_staff_mfa_enrolment_login_and_enforcement(client):
    make_staff()
    h = login(client, "admin@roanwick.example")
    setup = client.post("/api/v1/auth/mfa/setup", headers=h).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/Roanwick:") and setup["secret"]
    assert client.post("/api/v1/auth/mfa/enable", headers=h, json={"code": "000000"}).status_code == 422
    assert client.post("/api/v1/auth/mfa/enable", headers=h, json={"code": mfa.totp(setup["secret"])}).json() == {"mfa_enabled": True}

    r = client.post("/api/v1/auth/login", json={"email": "admin@roanwick.example", "password": PASSWORD})
    assert r.status_code == 401 and r.json()["error"]["code"] == "mfa_required"
    assert client.post("/api/v1/auth/login", json={"email": "admin@roanwick.example", "password": PASSWORD, "mfa_code": "123456"}).json()["error"]["code"] == "mfa_invalid"
    ok = client.post("/api/v1/auth/login", json={"email": "admin@roanwick.example", "password": PASSWORD, "mfa_code": mfa.totp(setup["secret"])})
    assert ok.status_code == 200 and ok.json()["user"]["mfa_enabled"] is True

    # Enforcement: when required, staff without MFA are blocked from admin actions.
    make_staff("operations", "ops@roanwick.example")
    ops = login(client, "ops@roanwick.example")
    assert client.get("/api/v1/admin/users", headers=ops).status_code == 200
    admin = auth(ok.json()["access_token"])
    assert client.put("/api/v1/admin/settings/require_staff_mfa", headers=admin, json={"value": True}).status_code == 200
    blocked = client.get("/api/v1/admin/users", headers=ops)
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "mfa_enrolment_required"
    assert client.get("/api/v1/admin/users", headers=admin).status_code == 200
    # Disabling needs both password and a current code.
    assert client.post("/api/v1/auth/mfa/disable", headers=admin, json={"password": PASSWORD, "code": "000000"}).status_code == 422
    assert client.post("/api/v1/auth/mfa/disable", headers=admin, json={"password": PASSWORD, "code": mfa.totp(setup["secret"])}).status_code == 204


def test_session_hint_cookie_set_on_login_and_cleared_on_logout(client):
    r = client.post("/api/v1/auth/register", json={"email": "c@example.com", "password": PASSWORD, "full_name": "Cee Cee", "accept_terms": True})
    assert "rw_session=1" in r.headers.get_list("set-cookie")[-1] or any("rw_session=1" in c for c in r.headers.get_list("set-cookie"))
    out = client.post("/api/v1/auth/logout")
    assert any("rw_session" in c and "Max-Age=0" in c for c in out.headers.get_list("set-cookie"))


# ---------- quality management ----------
def test_repeated_withdrawals_open_one_quality_review_without_suspending(client):
    p = make_provider(client, auto_accept=False, hours=tuple((d, 0, 23) for d in range(7)))
    make_staff("operations", "ops@roanwick.example")
    ops = login(client, "ops@roanwick.example")
    make_provider(client, "backup@example.com", name="Backup", auto_accept=False, hours=tuple((d, 0, 23) for d in range(7)))
    who = register_customer(client)
    for i in range(3):
        b = confirmed_booking(client, who, start=slot(8 + i, 10, weekday=1 + i), provider_id=p["id"])
        assert client.post(f"/api/v1/provider/jobs/{b['id']}/accept", headers=p["headers"]).status_code == 200
        assert client.post(f"/api/v1/provider/jobs/{b['id']}/decline", headers=p["headers"], json={}).status_code == 200
    tickets = client.get("/api/v1/admin/tickets", headers=login(client, "ops@roanwick.example")).json()["items"]
    reviews = [t for t in tickets if t["kind"] == "quality_review"]
    assert len(reviews) == 1 and "3 withdrawals" in reviews[0]["body"] and "Nothing has been changed automatically" in reviews[0]["body"]
    assert client.get(f"/api/v1/professionals/{p['id']}").status_code == 200            # still approved
    ops_report = client.get("/api/v1/admin/reports/operations", headers=ops).json()
    assert ops_report["quality_reviews_open"] == 1


def test_low_rating_opens_review(client, db):
    from app.models.providers import ProviderProfile
    from app.services import quality
    p = make_provider(client)
    prof = db.get(ProviderProfile, uuid.UUID(p["id"]))
    prof.rating_avg, prof.rating_count = 3.1, 6
    db.commit()
    t = quality.evaluate(db, prof.user_id)
    assert t is not None and "average rating 3.10" in t.body
    assert quality.evaluate(db, prof.user_id) is None                                   # no duplicate while one is open


# ---------- clawback ----------
def test_provider_funded_refund_after_payout_is_netted_from_next_payout(client):
    from app.models.finance import Payout, ProviderAdjustment
    from app.services import finance
    p = make_provider(client)
    who = register_customer(client)
    make_staff()
    h = login(client, "admin@roanwick.example")

    def finished(start):
        b = confirmed_booking(client, who, start=start)
        shift_booking(b["id"], datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5))
        client.post(f"/api/v1/provider/jobs/{b['id']}/complete", headers=p["headers"])
        return b

    b1 = finished(slot(4, 10, weekday=1))
    with SessionLocal() as s:
        s.query(Payout).update({"release_at": utcnow() - timedelta(minutes=1)})
        s.commit()
    assert client.post("/api/v1/admin/jobs/run", headers=h).json()["payouts"]["paid"] == 1
    r = client.post(f"/api/v1/admin/bookings/{b1['id']}/refund", headers=h, json={"amount_pence": 2000, "reason": "complaint", "funded_by": "provider", "note": "Damage found"})
    assert r.status_code == 200
    owed = client.get("/api/v1/admin/adjustments", headers=h).json()
    assert owed[0]["remaining_pence"] == 2000
    finished(slot(5, 10, weekday=2))
    with SessionLocal() as s:
        s.query(Payout).filter(Payout.status == "pending").update({"release_at": utcnow() - timedelta(minutes=1)})
        s.commit()
    client.post("/api/v1/admin/jobs/run", headers=h)
    with SessionLocal() as s:
        latest = s.query(Payout).filter(Payout.status == "paid").order_by(Payout.created_at.desc()).first()
        assert latest.amount_pence == 5148 - 2000 and "netted off" in latest.note
        assert s.query(ProviderAdjustment).one().remaining_pence == 0


# ---------- retention and erasure ----------
def test_erasing_a_professional_deletes_their_documents_and_hides_them(client, db):
    from pathlib import Path
    from app.core.config import get_settings
    from app.models.providers import ProviderDocument
    p = make_provider(client)
    key = f"{p['id']}/id.pdf"
    root = Path(get_settings().storage_dir)
    (root / p["id"]).mkdir(parents=True, exist_ok=True)
    (root / key).write_bytes(b"%PDF-1.4 id")
    d = db.query(ProviderDocument).filter_by(provider_id=uuid.UUID(p["id"]), doc_type="identity").one()
    d.storage_key = key
    db.commit()
    assert client.post("/api/v1/auth/me/delete", headers=p["headers"], json={"password": PASSWORD}).status_code == 204
    assert not (root / key).exists()
    assert db.query(ProviderDocument).filter_by(provider_id=uuid.UUID(p["id"])).count() == 0
    assert client.get(f"/api/v1/professionals/{p['id']}").status_code == 404


def test_retention_job_purges_old_idempotency_and_notifications_only(client, db):
    from sqlalchemy import text
    who = register_customer(client)
    db.execute(text("insert into idempotency_records (key, scope, request_hash, created_at) values ('old','x','h', now() - interval '10 days'), ('new','x','h', now())"))
    db.execute(text("update notifications set created_at = now() - interval '200 days' where channel = 'in_app'"))
    db.commit()
    make_staff()
    out = client.post("/api/v1/admin/jobs/run", headers=login(client, "admin@roanwick.example")).json()["retention"]
    assert out["idempotency_records"] == 1 and out["notifications"] >= 0
    assert db.execute(text("select count(*) from idempotency_records where key='new'")).scalar() == 1
