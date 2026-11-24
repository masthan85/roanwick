import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.db import SessionLocal, utcnow
from tests.conftest import *  # noqa


def finished_job(client, who, p, **kw):
    b = confirmed_booking(client, who, **kw)
    shift_booking(b["id"], datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5))
    assert client.post(f"/api/v1/provider/jobs/{b['id']}/complete", headers=p["headers"]).status_code == 200
    return b


def report(client, h):
    return client.get("/api/v1/admin/reports/finance", headers=h, params={"from": (date.today() - timedelta(days=2)).isoformat(), "to": (date.today() + timedelta(days=1)).isoformat()}).json()


def test_commission_payout_hold_and_release(client):
    from app.models.finance import Payout
    p = make_provider(client)
    who = register_customer(client)
    b = finished_job(client, who, p)                       # 3h at £22 = £66.00
    with SessionLocal() as s:
        po = s.query(Payout).one()
        assert (po.gross_pence, po.commission_pence, po.amount_pence) == (6600, 1452, 5148)       # 22% commission
        assert po.status == "pending" and po.release_at > utcnow() + timedelta(days=2)
    make_staff()
    h = login(client, "admin@roanwick.example")
    assert client.post("/api/v1/admin/jobs/run", headers=h).json()["payouts"]["paid"] == 0       # still inside the hold period
    with SessionLocal() as s:
        s.query(Payout).update({"release_at": utcnow() - timedelta(minutes=1)})
        s.commit()
    assert client.post("/api/v1/admin/jobs/run", headers=h).json()["payouts"]["paid"] == 1
    assert client.post("/api/v1/admin/jobs/run", headers=h).json()["payouts"]["paid"] == 0       # not paid twice
    e = client.get("/api/v1/provider/earnings", headers=p["headers"]).json()
    assert e["paid_pence"] == 5148 and e["pending_pence"] == 0


def test_open_complaint_holds_payout(client):
    from app.models.finance import Payout
    p = make_provider(client)
    who = register_customer(client)
    b = finished_job(client, who, p)
    client.post(f"/api/v1/bookings/{b['id']}/complaints", headers=who["headers"], json={"category": "quality", "description": "Kitchen floor was left sticky."})
    with SessionLocal() as s:
        s.query(Payout).update({"release_at": utcnow() - timedelta(minutes=1)})
        s.commit()
    make_staff()
    res = client.post("/api/v1/admin/jobs/run", headers=login(client, "admin@roanwick.example")).json()
    assert res["payouts"]["paid"] == 0 and res["payouts"]["held"] == 1


def test_financial_report_separates_gbv_revenue_and_costs(client):
    p = make_provider(client)
    who = register_customer(client)
    finished_job(client, who, p)                                      # £66.00 gross
    make_staff("finance", "fin@roanwick.example")
    h = login(client, "fin@roanwick.example")
    r = report(client, h)
    assert r["gross_booking_value"] == {"value": 6600, "basis": "actual", "note": r["gross_booking_value"]["note"]}
    assert r["platform_revenue"]["value"] == 1452                      # commission only, not £66
    assert r["provider_earnings"]["value"] == 5148
    assert r["processing_costs"]["value"] == 119 and r["processing_costs"]["basis"] == "actual"    # 1.5% + 20p from the (sandbox) processor data
    assert r["contribution"]["value"] == 1452 - 119
    assert r["contribution_per_booking"]["value"] == 1333
    assert r["provider_payouts_owed"]["value"] == 5148
    assert r["customer_acquisition_cost"]["value"] is None             # no marketing spend entered yet
    assert r["lifetime_value_estimate"]["basis"] == "estimated"

    assert client.post("/api/v1/admin/costs", headers=h, json={"category": "marketing", "channel": "google_ads", "period_start": date.today().isoformat(), "period_end": date.today().isoformat(), "amount_pence": 5000}).status_code == 201
    r = report(client, h)
    assert r["customer_acquisition_cost"] == {"value": 5000, "basis": "manual", "note": r["customer_acquisition_cost"]["note"]}
    assert r["manual_costs"]["by_category"] == {"marketing": 5000}
    assert r["by_area"][0]["key"] == "SW11" and r["by_service"][0]["key"] == "Regular home cleaning"


def test_platform_funded_refund_reduces_contribution_and_provider_funded_reduces_payout(client):
    from app.models.finance import Payout
    p = make_provider(client)
    who = register_customer(client)
    b = finished_job(client, who, p)
    make_staff("super_admin", "admin@roanwick.example")
    h = login(client, "admin@roanwick.example")
    assert client.post(f"/api/v1/admin/bookings/{b['id']}/refund", headers=h, json={"amount_pence": 1000, "reason": "goodwill", "funded_by": "platform", "note": "Missed a room"}).status_code == 200
    r = report(client, h)
    assert r["platform_funded_refunds"]["value"] == 1000 and r["contribution"]["value"] == 1452 - 119 - 1000 and r["refunds_issued"]["value"] == 1000
    assert client.post(f"/api/v1/admin/bookings/{b['id']}/refund", headers=h, json={"amount_pence": 500, "reason": "complaint", "funded_by": "provider", "note": "Damage"}).status_code == 200
    with SessionLocal() as s:
        assert s.query(Payout).one().amount_pence == 5148 - 500
    over = client.post(f"/api/v1/admin/bookings/{b['id']}/refund", headers=h, json={"amount_pence": 10**6, "reason": "other", "funded_by": "platform", "note": "Too much"})
    assert over.status_code == 422 and over.json()["error"]["code"] == "refund_exceeds_paid"


def test_commission_override_and_setting_drive_payout(client):
    from app.models.finance import Payout
    p = make_provider(client)
    make_staff()
    h = login(client, "admin@roanwick.example")
    client.put("/api/v1/admin/settings/commission_bps", headers=h, json={"value": 1500})
    who = register_customer(client)
    finished_job(client, who, p)
    with SessionLocal() as s:
        assert s.query(Payout).one().commission_pence == 990
    client.patch(f"/api/v1/admin/providers/{p['id']}/commission", headers=h, json={"commission_override_bps": 1000})
    finished_job(client, who, p, start=slot(5, 10, weekday=2))
    with SessionLocal() as s:
        assert sorted(x.commission_pence for x in s.query(Payout)) == [660, 990]


def test_promotion_and_referral_economics(client):
    p = make_provider(client)
    make_staff()
    h = login(client, "admin@roanwick.example")
    assert client.post("/api/v1/admin/promotions", headers=h, json={"code": "first10", "kind": "percent", "value": 1000, "first_booking_only": True, "description": "10% off"}).status_code == 201
    referrer = register_customer(client, "ref@example.com")
    code = client.get("/api/v1/me/referral", headers=referrer["headers"]).json()["code"]
    friend = register_customer(client, "friend@example.com", referral_code=code)
    q = quote(client, friend, promo_code="FIRST10")
    assert q["discount_pence"] == 660 and q["total_pence"] == 6600 - 660
    start = slot(4, 10, weekday=1)
    b = confirmed_booking(client, friend, start=start, qid=q["id"])
    assert b["total_pence"] == 5940
    shift_booking(b["id"], datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5))
    client.post(f"/api/v1/provider/jobs/{b['id']}/complete", headers=p["headers"])
    assert client.get("/api/v1/me/referral", headers=referrer["headers"]).json()["credit_pence"] == 1000
    assert client.get("/api/v1/me/referral", headers=friend["headers"]).json()["credit_pence"] == 1000
    # Revenue is net of the promotion the platform funded: commission on full service value less the discount.
    r = report(client, login(client, "admin@roanwick.example"))
    assert r["promotion_cost"]["value"] == 660 and r["platform_revenue"]["value"] == 1452 - 660
    # Used code is single-use; referral credit then pays part of the next booking.
    assert client.post("/api/v1/quotes", headers=friend["headers"], json={"offering_id": offering_id(client), "postcode": "SW11 1AB", "minutes": 120, "promo_code": "FIRST10"}).json()["error"]["code"] in ("promo_used", "promo_first_only")
    q2 = quote(client, friend, minutes=120)
    b2 = confirmed_booking(client, friend, start=slot(5, 10, weekday=2), qid=q2["id"], use_credit=True)
    assert b2["payment"]["credit_applied_pence"] == 1000 and b2["payment"]["amount_pence"] == 4400 - 1000
    assert client.get("/api/v1/me/referral", headers=friend["headers"]).json()["credit_pence"] == 0
    cancelled = client.post(f"/api/v1/bookings/{b2['id']}/cancel", headers=friend["headers"], json={}).json()
    assert cancelled["refund_pence"] == 4400 and client.get("/api/v1/me/referral", headers=friend["headers"]).json()["credit_pence"] == 1000   # credit portion returns as credit


def test_recurring_plan_only_charges_inside_the_horizon(client):
    make_provider(client)
    who = register_customer(client)
    addr = add_address(client, who)
    body = {"offering_id": offering_id(client), "address_id": addr, "frequency": "weekly", "start_time": "10:00:00", "minutes": 180, "accept_terms": True}
    r = client.post("/api/v1/subscriptions", headers=who["headers"], json={**body, "first_visit_on": slot(5, 10, weekday=2).date().isoformat()})
    assert r.status_code == 201 and r.json()["generation"]["created"] == 1          # the second visit is beyond the 8-day window
    from app.models.finance import Payment
    with SessionLocal() as s:
        assert s.query(Payment).filter_by(status="succeeded").count() == 1
    later = client.post("/api/v1/subscriptions", headers=who["headers"], json={**body, "first_visit_on": slot(30, 10, weekday=3).date().isoformat()})
    assert later.status_code == 201 and later.json()["generation"]["created"] == 0 and "closer to the date" in later.json()["note"]


def test_recurring_plan_generates_visits_for_preferred_professional(client):
    p1 = make_provider(client, "p1@example.com", name="Pro One")
    p2 = make_provider(client, "p2@example.com", name="Pro Two")
    make_staff()
    client.put("/api/v1/admin/settings/plan_horizon_days", headers=login(client, "admin@roanwick.example"), json={"value": 45})
    who = register_customer(client)
    addr = add_address(client, who)
    first = slot(5, 10, weekday=2).date()
    r = client.post("/api/v1/subscriptions", headers=who["headers"], json={"offering_id": offering_id(client), "address_id": addr, "frequency": "weekly", "first_visit_on": first.isoformat(),
                                                                          "start_time": "10:00:00", "minutes": 180, "preferred_provider_id": p2["id"], "accept_terms": True})
    assert r.status_code == 201, r.text
    assert r.json()["generation"]["created"] >= 4
    bookings = client.get("/api/v1/bookings", headers=who["headers"]).json()["items"]
    assert all(b["professional"]["id"] == p2["id"] and b["status"] == "confirmed" for b in bookings)
    assert all(b["total_pence"] == 6600 - 660 for b in bookings)                  # weekly plan discount
    sid = r.json()["id"]
    paused = client.post(f"/api/v1/subscriptions/{sid}/actions", headers=who["headers"], json={"action": "cancel"}).json()
    assert paused["status"] == "cancelled"
    assert all(b["status"] == "cancelled" for b in client.get("/api/v1/bookings", headers=who["headers"]).json()["items"])
