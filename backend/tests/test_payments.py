import json
import uuid
from datetime import timedelta

from app.core.config import get_settings
from app.services.payments import sign_sandbox
from tests.conftest import *  # noqa


def webhook(client, event, sig=None):
    body = json.dumps(event).encode()
    return client.post("/api/v1/webhooks/payments", content=body, headers={"X-Sandbox-Signature": sig if sig is not None else sign_sandbox(body), "Content-Type": "application/json"})


def held_booking(client):
    make_provider(client)
    who = register_customer(client)
    b = book(client, who, slot(4, 10, weekday=1)).json()
    return who, b


def external_id(booking_id):
    from app.models.finance import Payment
    from sqlalchemy import select
    with SessionLocal() as s:
        return s.scalar(select(Payment.external_id).where(Payment.booking_id == uuid.UUID(booking_id))), s.scalar(select(Payment.amount_pence).where(Payment.booking_id == uuid.UUID(booking_id)))


def test_declined_card_then_retry_succeeds_without_duplicate_booking(client):
    who, b = held_booking(client)
    r = pay(client, who, b["id"], "pm_card_declined")
    assert r.status_code == 402 and r.json()["error"]["code"] == "payment_failed"
    assert "declined" in r.json()["error"]["message"]
    cur = client.get(f"/api/v1/bookings/{b['id']}", headers=who["headers"]).json()
    assert cur["status"] == "pending_payment" and cur["payment"]["status"] == "failed"
    ok = pay(client, who, b["id"], "pm_card_visa")
    assert ok.status_code == 200 and ok.json()["status"] == "confirmed"
    assert len(client.get("/api/v1/bookings", headers=who["headers"]).json()["items"]) == 1


def test_pay_is_idempotent(client):
    who, b = held_booking(client)
    a = pay(client, who, b["id"], key="pay-1")
    again = pay(client, who, b["id"], key="pay-1")
    assert a.status_code == again.status_code == 200 and a.json() == again.json()
    from app.models.finance import Payment
    with SessionLocal() as s:
        assert s.query(Payment).filter_by(booking_id=uuid.UUID(b["id"]), status="succeeded").count() == 1
    clash = pay(client, who, b["id"], "pm_card_declined", key="pay-1")
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "idempotency_key_reused"


def test_webhook_signature_required(client):
    who, b = held_booking(client)
    ext, amt = external_id(b["id"])
    ev = {"id": "evt_1", "type": "payment_intent.succeeded", "data": {"external_id": ext, "amount": amt, "fee": 99}}
    assert webhook(client, ev, sig="deadbeef").status_code == 400
    assert client.get(f"/api/v1/bookings/{b['id']}", headers=who["headers"]).json()["status"] == "pending_payment"
    assert webhook(client, ev).status_code == 200
    assert client.get(f"/api/v1/bookings/{b['id']}", headers=who["headers"]).json()["status"] == "confirmed"


def test_webhook_duplicate_delivery_applied_once(client):
    who, b = held_booking(client)
    ext, amt = external_id(b["id"])
    ev = {"id": "evt_dup", "type": "payment_intent.succeeded", "data": {"external_id": ext, "amount": amt, "fee": 50}}
    assert webhook(client, ev).json()["outcome"] == "processed"
    assert webhook(client, ev).json()["outcome"] == "duplicate"
    from app.models.bookings import BookingStatusHistory
    with SessionLocal() as s:
        assert s.query(BookingStatusHistory).filter_by(booking_id=uuid.UUID(b["id"]), to_status="confirmed").count() == 1


def test_webhook_failure_is_recorded_and_retry_succeeds(client):
    who, b = held_booking(client)
    ev = {"id": "evt_early", "type": "payment_intent.succeeded", "data": {"external_id": "pi_sbx_unknown", "amount": 100, "fee": 1}}
    assert webhook(client, ev).status_code == 500
    from app.models.system import WebhookEvent
    with SessionLocal() as s:
        row = s.get(WebhookEvent, "evt_early")
        assert row.status == "failed" and row.attempts == 1
    ext, amt = external_id(b["id"])
    fixed = {**ev, "data": {"external_id": ext, "amount": amt, "fee": 1}}
    assert webhook(client, fixed).status_code == 200      # provider redelivers the same id after we are ready
    with SessionLocal() as s:
        row = s.get(WebhookEvent, "evt_early")
        assert row.status == "processed" and row.attempts == 2


def test_webhook_amount_mismatch_rejected(client):
    who, b = held_booking(client)
    ext, amt = external_id(b["id"])
    assert webhook(client, {"id": "evt_bad", "type": "payment_intent.succeeded", "data": {"external_id": ext, "amount": amt - 1, "fee": 1}}).status_code == 500
    assert client.get(f"/api/v1/bookings/{b['id']}", headers=who["headers"]).json()["status"] == "pending_payment"


def test_late_payment_after_hold_expiry_is_refunded(client, db):
    from app.models.bookings import Booking
    from app.models.finance import Refund
    who, b = held_booking(client)
    ext, amt = external_id(b["id"])
    bk = db.get(Booking, uuid.UUID(b["id"]))
    from datetime import datetime, timezone
    bk.hold_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()
    other = register_customer(client, "other@example.com")
    assert book(client, other, slot(4, 10, weekday=1)).status_code == 201     # slot released and re-taken
    webhook(client, {"id": "evt_late", "type": "payment_intent.succeeded", "data": {"external_id": ext, "amount": amt, "fee": 10}})
    with SessionLocal() as s:
        refunds = s.query(Refund).filter_by(booking_id=uuid.UUID(b["id"])).all()
        assert len(refunds) == 1 and refunds[0].amount_pence == amt
    assert client.get(f"/api/v1/bookings/{b['id']}", headers=who["headers"]).json()["status"] == "expired"


def test_payment_history_and_credit(client):
    who, b = held_booking(client)
    pay(client, who, b["id"])
    hist = client.get("/api/v1/payments", headers=who["headers"]).json()
    assert hist["total"] == 1 and hist["items"][0]["status"] == "succeeded"
