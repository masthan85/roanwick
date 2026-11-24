import uuid
from datetime import date, datetime, timedelta, timezone

from app.core.db import SessionLocal
from tests.conftest import *  # noqa


def run_jobs(client):
    make_staff("super_admin", "root@roanwick.example")
    return client.post("/api/v1/admin/jobs/run", headers=login(client, "root@roanwick.example")).json()


def test_document_expiry_reminder_sent_once(client, db):
    from app.models.engagement import Notification
    from app.models.providers import ProviderDocument
    from sqlalchemy import select
    p = make_provider(client, insurance_days=10)
    out = run_jobs(client)
    assert out["document_reminders"] == 1
    assert run_jobs_again(client)["document_reminders"] == 0       # not repeated for the same expiry date
    note = db.scalar(select(Notification).where(Notification.user_id == uuid.UUID(p["id"]), Notification.template == "document_expiry", Notification.channel == "in_app"))
    assert "expires soon" in note.subject


def run_jobs_again(client):
    return client.post("/api/v1/admin/jobs/run", headers=login(client, "root@roanwick.example")).json()


def test_unaccepted_job_is_rematched_by_the_job(client, db):
    from app.models.bookings import Booking
    p1 = make_provider(client, "p1@example.com", name="Pro One", auto_accept=False)
    p2 = make_provider(client, "p2@example.com", name="Pro Two", auto_accept=False)
    who = register_customer(client)
    b = confirmed_booking(client, who)
    first = b["professional"]["id"]
    bk = db.get(Booking, uuid.UUID(b["id"]))
    from sqlalchemy import text
    db.execute(text("update bookings set updated_at = now() - interval '6 hours' where id = :i"), {"i": b["id"]})
    db.commit()
    out = run_jobs(client)
    assert out["acceptance_timeouts"] == 1
    now = client.get(f"/api/v1/bookings/{b['id']}", headers=who["headers"]).json()
    assert now["professional"]["id"] != first


def test_queued_email_is_dispatched_and_marked_sent(client, db):
    from app.models.engagement import Notification
    from sqlalchemy import select
    register_customer(client)
    assert db.scalar(select(Notification.status).where(Notification.channel == "email")) == "queued"
    assert run_jobs(client)["notifications"]["sent"] >= 1
    db.expire_all()
    assert db.scalar(select(Notification.status).where(Notification.channel == "email").limit(1)) == "sent"


def test_security_headers_and_error_shape(client):
    r = client.get("/api/v1/catalogue/categories")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY" and r.headers["x-request-id"]
    e = client.get("/api/v1/bookings").json()["error"]
    assert set(e) == {"code", "message", "details", "request_id"} and e["code"] == "unauthorised"
    assert client.post("/api/v1/quotes", json={"offering_id": "nope"}).json()["error"]["code"] == "validation_error"
    assert client.get("/api/v1/does-not-exist").json()["error"]["code"] == "not_found"


def test_pagination_bounds(client):
    who = register_customer(client)
    assert client.get("/api/v1/bookings?page_size=1000", headers=who["headers"]).status_code == 422
    assert client.get("/api/v1/bookings?page=0", headers=who["headers"]).status_code == 422
    r = client.get("/api/v1/bookings?page=1&page_size=5", headers=who["headers"]).json()
    assert r == {"items": [], "total": 0, "page": 1, "page_size": 5}


def test_tokens_cannot_be_forged_or_reused_across_purposes(client):
    from app.core.security import create_purpose_token
    who = register_customer(client)
    reset = create_purpose_token(uuid.UUID(who["id"]), "reset_password", 10)
    assert client.get("/api/v1/auth/me", headers=auth(reset)).status_code == 401            # a reset token is not an access token
    assert client.get("/api/v1/auth/me", headers=auth("a.b.c")).status_code == 401
    import jwt
    forged = jwt.encode({"sub": who["id"], "type": "access", "roles": ["super_admin"], "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256")
    assert client.get("/api/v1/admin/users", headers=auth(forged)).status_code == 401


def test_admin_cannot_download_documents_without_permission_and_views_are_audited(client, tmp_path):
    import io
    p = make_provider(client)
    make_staff("support", "support@roanwick.example")
    make_staff("operations", "ops@roanwick.example")
    from app.models.providers import ProviderDocument
    from app.core.config import get_settings
    from pathlib import Path
    with SessionLocal() as s:
        d = s.query(ProviderDocument).first()
        d.storage_key = f"{p['id']}/test.pdf"
        (Path(get_settings().storage_dir) / p["id"]).mkdir(parents=True, exist_ok=True)
        (Path(get_settings().storage_dir) / d.storage_key).write_bytes(b"%PDF-1.4 secret")
        s.commit()
        did = str(d.id)
    assert client.get(f"/api/v1/admin/documents/{did}/download", headers=login(client, "support@roanwick.example")).status_code == 403
    ok = client.get(f"/api/v1/admin/documents/{did}/download", headers=login(client, "ops@roanwick.example"))
    assert ok.status_code == 200 and ok.content.startswith(b"%PDF") and ok.headers["cache-control"] == "no-store"
    from app.models.identity import AuditEvent
    with SessionLocal() as s:
        assert s.query(AuditEvent).filter_by(action="document.viewed").count() == 1
    assert client.get(f"/api/v1/admin/documents/{uuid.uuid4()}/download", headers=login(client, "ops@roanwick.example")).status_code == 404
