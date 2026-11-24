from datetime import timedelta

from datetime import datetime
from zoneinfo import ZoneInfo

from tests.conftest import *  # noqa


def cancel(client, who, bid, reason="Plans changed"):
    return client.post(f"/api/v1/bookings/{bid}/cancel", headers=who["headers"], json={"reason": reason})


def setup(client):
    p = make_provider(client)
    who = register_customer(client)
    return p, who, confirmed_booking(client, who)


def test_cancellation_refund_tiers(client):
    now = datetime.now(LONDON)
    cases = [(timedelta(hours=72), 10000), (timedelta(hours=36), 5000), (timedelta(hours=10), 0)]
    for i, (lead, bps) in enumerate(cases):
        make_provider(client, f"p{i}@example.com", name=f"P{i}", hours=tuple((d, 0, 23) for d in range(7)))
    who = register_customer(client)
    for i, (lead, bps) in enumerate(cases):
        b = confirmed_booking(client, who, start=slot(10 + i, 10, weekday=1 + i), addr=None)
        start = (now + lead).replace(minute=0, second=0, microsecond=0)
        shift_booking(b["id"], start.astimezone(ZoneInfo("UTC")))
        preview = client.get(f"/api/v1/bookings/{b['id']}/cancellation-preview", headers=who["headers"]).json()
        assert preview["refund_bps"] == bps
        res = cancel(client, who, b["id"]).json()
        assert res["refund_pence"] == round(b["total_pence"] * bps / 10000)
        assert res["refund_pence"] + res["retained_pence"] == b["total_pence"]
        assert res["booking"]["status"] == "cancelled"


def test_late_cancellation_pays_provider_compensation(client):
    p, who, b = setup(client)
    shift_booking(b["id"], (datetime.now(LONDON) + timedelta(hours=10)).astimezone(ZoneInfo("UTC")))
    cancel(client, who, b["id"])
    earnings = client.get("/api/v1/provider/earnings", headers=p["headers"]).json()
    assert earnings["payouts"]["total"] == 1
    po = earnings["payouts"]["items"][0]
    assert po["service_value_pence"] == b["total_pence"] and po["commission_pence"] == round(b["total_pence"] * 0.22)


def test_cancelling_unpaid_booking_frees_slot_with_no_charge(client):
    make_provider(client)
    who = register_customer(client)
    b = book(client, who, slot(4, 10, weekday=1)).json()
    res = cancel(client, who, b["id"]).json()
    assert res["refund_pence"] == 0 and res["booking"]["status"] == "cancelled"
    assert book(client, register_customer(client, "x@example.com"), slot(4, 10, weekday=1)).status_code == 201


def test_reschedule_rules(client):
    p, who, b = setup(client)
    new = slot(6, 14, weekday=2)
    r = client.post(f"/api/v1/bookings/{b['id']}/reschedule", headers=who["headers"], json={"starts_at": new.isoformat()})
    assert r.status_code == 200 and r.json()["starts_at"].startswith(new.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M"))
    # Provider busy at the new time -> conflict unless another professional is allowed.
    other = register_customer(client, "o@example.com")
    confirmed_booking(client, other, start=slot(7, 10, weekday=3))
    clash = client.post(f"/api/v1/bookings/{b['id']}/reschedule", headers=who["headers"], json={"starts_at": slot(7, 10, weekday=3).isoformat()})
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "provider_unavailable"
    shift_booking(b["id"], (datetime.now(LONDON) + timedelta(hours=30)).astimezone(ZoneInfo("UTC")))
    late = client.post(f"/api/v1/bookings/{b['id']}/reschedule", headers=who["headers"], json={"starts_at": slot(9, 10, weekday=1).isoformat()})
    assert late.status_code == 422 and late.json()["error"]["code"] == "too_late_to_reschedule"


def test_provider_decline_rematches_then_leaves_unassigned_for_ops(client):
    p1 = make_provider(client, "p1@example.com", name="Pro One", auto_accept=False)
    p2 = make_provider(client, "p2@example.com", name="Pro Two", auto_accept=False)
    who = register_customer(client)
    b = confirmed_booking(client, who)
    assert b["status"] == "awaiting_provider"
    first = b["professional"]["id"]
    first_h = (p1 if p1["id"] == first else p2)["headers"]
    second_h = (p2 if p1["id"] == first else p1)["headers"]
    assert client.post(f"/api/v1/provider/jobs/{b['id']}/decline", headers=first_h, json={}).status_code == 200
    now = client.get(f"/api/v1/bookings/{b['id']}", headers=who["headers"]).json()
    assert now["professional"]["id"] != first and now["status"] == "awaiting_provider"
    assert client.post(f"/api/v1/provider/jobs/{b['id']}/decline", headers=second_h, json={}).status_code == 200
    now = client.get(f"/api/v1/bookings/{b['id']}", headers=who["headers"]).json()
    assert now["professional"] is None and now["status"] == "awaiting_provider"
    # Customer can walk away with a full refund when nobody is assigned.
    res = cancel(client, who, b["id"]).json()
    assert res["refund_pence"] == b["total_pence"]


def test_provider_accept_and_job_progress(client):
    p = make_provider(client, auto_accept=False)
    who = register_customer(client)
    b = confirmed_booking(client, who)
    assert b["status"] == "awaiting_provider"
    jobs = client.get("/api/v1/provider/jobs", headers=p["headers"]).json()["items"]
    assert jobs[0]["address"] == {"postcode": "SW11", "city": "London"}          # address withheld until accepted
    assert client.post(f"/api/v1/provider/jobs/{b['id']}/accept", headers=p["headers"]).json()["status"] == "confirmed"
    assert client.get(f"/api/v1/provider/jobs/{b['id']}", headers=p["headers"]).json()["address"]["line1"] == "12 Example Road"
    assert client.post(f"/api/v1/provider/jobs/{b['id']}/start", headers=p["headers"]).status_code == 422   # too early
    shift_booking(b["id"], datetime.now(ZoneInfo("UTC")) - timedelta(minutes=30))
    assert client.post(f"/api/v1/provider/jobs/{b['id']}/start", headers=p["headers"]).json()["status"] == "in_progress"
    assert client.post(f"/api/v1/provider/jobs/{b['id']}/complete", headers=p["headers"]).json()["status"] == "completed"
    assert client.post(f"/api/v1/provider/jobs/{b['id']}/complete", headers=p["headers"]).status_code == 409
    metrics = client.get("/api/v1/provider/metrics", headers=p["headers"]).json()
    assert metrics["jobs_completed"] == 1 and metrics["on_time_rate"] == 0.0     # started 30 minutes after the slot began


def test_other_provider_cannot_touch_job(client):
    p1 = make_provider(client, "p1@example.com")
    p2 = make_provider(client, "p2@example.com", areas=("SW4",))
    who = register_customer(client)
    b = confirmed_booking(client, who, provider_id=p1["id"])
    assert client.get(f"/api/v1/provider/jobs/{b['id']}", headers=p2["headers"]).status_code == 404
    assert client.post(f"/api/v1/provider/jobs/{b['id']}/complete", headers=p2["headers"]).status_code == 404


def test_messaging_between_parties(client):
    p, who, b = setup(client)
    other = register_customer(client, "snoop@example.com")
    assert client.post(f"/api/v1/bookings/{b['id']}/messages", headers=who["headers"], json={"body": "Key is under the mat."}).status_code == 201
    assert client.post(f"/api/v1/bookings/{b['id']}/messages", headers=p["headers"], json={"body": "Thanks, see you then."}).status_code == 201
    msgs = client.get(f"/api/v1/bookings/{b['id']}/messages", headers=p["headers"]).json()
    assert [m["sender_role"] for m in msgs] == ["customer", "professional"]
    assert client.get(f"/api/v1/bookings/{b['id']}/messages", headers=other["headers"]).status_code == 404
    assert client.post(f"/api/v1/bookings/{b['id']}/messages", headers=other["headers"], json={"body": "hi"}).status_code == 404


def complete(client, p, b):
    shift_booking(b["id"], datetime.now(ZoneInfo("UTC")) - timedelta(minutes=5))
    return client.post(f"/api/v1/provider/jobs/{b['id']}/complete", headers=p["headers"])


def test_reviews_update_rating_and_favourites(client):
    p, who, b = setup(client)
    assert client.post(f"/api/v1/bookings/{b['id']}/review", headers=who["headers"], json={"rating": 5, "punctuality": 5}).status_code == 409   # not completed yet
    assert client.put(f"/api/v1/favourites/{p['id']}", headers=who["headers"]).status_code == 403
    assert complete(client, p, b).status_code == 200
    r = client.post(f"/api/v1/bookings/{b['id']}/review", headers=who["headers"], json={"rating": 4, "punctuality": 5, "comment": "Spotless."})
    assert r.status_code == 201
    assert client.post(f"/api/v1/bookings/{b['id']}/review", headers=who["headers"], json={"rating": 4, "punctuality": 5}).status_code == 409
    assert client.get(f"/api/v1/professionals/{p['id']}").json()["rating_avg"] == 4.0
    assert client.put(f"/api/v1/favourites/{p['id']}", headers=who["headers"]).status_code == 204
    assert client.get("/api/v1/favourites", headers=who["headers"]).json()[0]["id"] == p["id"]
    rid = client.get("/api/v1/provider/reviews", headers=p["headers"]).json()[0]["id"]
    assert client.post(f"/api/v1/provider/reviews/{rid}/reply", headers=p["headers"], json={"reply": "Thank you!"}).status_code == 204
    assert client.get(f"/api/v1/professionals/{p['id']}").json()["reviews"][0]["reply"] == "Thank you!"


def test_complaint_and_refund_request_flow(client):
    p, who, b = setup(client)
    assert client.post(f"/api/v1/bookings/{b['id']}/complaints", headers=who["headers"], json={"category": "quality", "description": "Bathroom was not cleaned properly."}).status_code == 409
    complete(client, p, b)
    c = client.post(f"/api/v1/bookings/{b['id']}/complaints", headers=who["headers"], json={"category": "damage", "description": "A glass shelf was chipped during the clean."})
    assert c.status_code == 201
    assert client.get("/api/v1/complaints", headers=who["headers"]).json()[0]["status"] == "open"
    rr = client.post(f"/api/v1/bookings/{b['id']}/refund-requests", headers=who["headers"], json={"reason": "Part of the clean was missed.", "requested_pence": 1000})
    assert rr.status_code == 201
    assert client.post(f"/api/v1/bookings/{b['id']}/refund-requests", headers=who["headers"], json={"reason": "Same again please."}).status_code == 409
    assert client.post(f"/api/v1/bookings/{b['id']}/refund-requests", headers=who["headers"], json={"reason": "Way too much please.", "requested_pence": 10**7}).status_code in (409, 422)
