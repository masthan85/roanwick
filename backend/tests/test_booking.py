import threading
import uuid

from sqlalchemy.exc import IntegrityError

from datetime import timedelta

from tests.conftest import *  # noqa


def test_itemised_quote(client):
    r = client.post("/api/v1/quotes", json={"offering_id": offering_id(client), "postcode": "sw11 1ab", "minutes": 180, "addons": ["oven"], "frequency": "weekly"})
    assert r.status_code == 201
    q = r.json()
    kinds = [l["kind"] for l in q["lines"]]
    assert kinds == ["labour", "addon", "discount"]
    assert q["lines"][0]["amount_pence"] == 6600          # 3h at 22.00
    assert q["lines"][1]["amount_pence"] == 2500
    assert q["lines"][2]["amount_pence"] == -660          # 10% of labour only
    assert q["total_pence"] == 6600 + 2500 - 660
    assert q["duration_minutes"] == 180 + 45
    assert q["postcode"] == "SW11 1AB" and q["terms"]["tiers"]


def test_quote_rejects_uncovered_postcode_and_bad_input(client):
    oid = offering_id(client)
    r = client.post("/api/v1/quotes", json={"offering_id": oid, "postcode": "E1 6AN", "minutes": 120})
    assert r.status_code == 422 and r.json()["error"]["code"] == "outside_coverage"
    assert client.post("/api/v1/quotes", json={"offering_id": oid, "postcode": "nonsense", "minutes": 120}).json()["error"]["code"] == "invalid_postcode"
    assert client.post("/api/v1/quotes", json={"offering_id": oid, "postcode": "SW11 1AB", "minutes": 45}).status_code == 422


def test_end_of_tenancy_tiered_price(client):
    r = client.post("/api/v1/quotes", json={"offering_id": offering_id(client, "end-of-tenancy-cleaning"), "postcode": "SW12 9AA", "bedrooms": 2, "addons": ["carpets"]})
    assert r.status_code == 201 and r.json()["total_pence"] == 25000 + 6000 and r.json()["duration_minutes"] == 420


def test_slot_search_only_shows_bookable_times(client):
    make_provider(client)
    d = slot(4, 10, weekday=1).date().isoformat()
    r = client.get("/api/v1/catalogue/slots", params={"offering": "regular-cleaning", "postcode": "SW11 1AB", "minutes": 180, "from_date": d, "days": 1})
    assert r.status_code == 200
    times = [s["time"] for s in r.json()["days"][d]]
    assert "08:00" in times and "15:00" in times
    assert "15:30" not in times  # 3h would run past the 18:00 finish
    assert "07:30" not in times
    none = client.get("/api/v1/catalogue/slots", params={"offering": "regular-cleaning", "postcode": "SW19 1AB", "minutes": 180, "from_date": d, "days": 1})
    assert none.json()["days"] == {}


def test_double_booking_blocked_single_provider(client):
    make_provider(client)
    a, b = register_customer(client, "a@example.com"), register_customer(client, "b@example.com")
    start = slot(4, 10, weekday=1)
    assert book(client, a, start).status_code == 201
    r = book(client, b, start)
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_availability"
    # Overlap by a few minutes is also blocked, including the 30-minute travel buffer.
    assert book(client, b, start.replace(hour=12, minute=30)).status_code == 409
    assert book(client, b, start.replace(hour=13, minute=30)).status_code == 201


def test_two_providers_share_demand(client):
    p1 = make_provider(client, "p1@example.com", name="Pro One")
    p2 = make_provider(client, "p2@example.com", name="Pro Two")
    a, b = register_customer(client, "a@example.com"), register_customer(client, "b@example.com")
    start = slot(4, 10, weekday=2)
    r1, r2 = book(client, a, start), book(client, b, start)
    assert r1.status_code == r2.status_code == 201
    names = {r1.json()["professional"]["display_name"], r2.json()["professional"]["display_name"]}
    assert names == {"Pro One", "Pro Two"}
    assert book(client, register_customer(client, "c@example.com"), start).status_code == 409


def test_database_constraint_blocks_overlap_even_without_app_checks(client, db):
    from app.models.bookings import Booking
    from app.models.catalogue import ServiceOffering
    from sqlalchemy import select
    import copy

    p = make_provider(client)
    who = register_customer(client)
    existing = confirmed_booking(client, who)
    src = db.get(Booking, uuid.UUID(existing["id"]))
    clone = Booking(reference="RW-TESTDUPE", customer_id=src.customer_id, provider_id=src.provider_id, offering_id=src.offering_id, status="confirmed",
                    starts_at=src.starts_at + timedelta(minutes=30), ends_at=src.ends_at, blocked_until=src.blocked_until, address_snapshot={}, outward_code="SW11", total_pence=1)
    db.add(clone)
    try:
        db.flush()
        raise AssertionError("overlapping insert should have been rejected by the exclusion constraint")
    except IntegrityError as e:
        assert getattr(e.orig, "sqlstate", None) == "23P01"
        db.rollback()


def test_concurrent_requests_cannot_double_book(client):
    make_provider(client)
    customers = [register_customer(client, f"c{i}@example.com") for i in range(8)]
    start = slot(5, 11, weekday=3)
    qids = [quote(client, c)["id"] for c in customers]
    addrs = [add_address(client, c) for c in customers]
    results, barrier = [], threading.Barrier(len(customers))

    def attempt(i):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as cl:
            barrier.wait()
            results.append(book(cl, customers[i], start, qid=qids[i], addr=addrs[i]).status_code)

    ts = [threading.Thread(target=attempt, args=(i,)) for i in range(len(customers))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(results) == [201] + [409] * 7, results


def test_booking_idempotency(client):
    make_provider(client)
    who = register_customer(client)
    start = slot(4, 10, weekday=1)
    qid, addr = quote(client, who)["id"], add_address(client, who)
    r1 = book(client, who, start, qid=qid, addr=addr, key="req-1")
    r2 = book(client, who, start, qid=qid, addr=addr, key="req-1")
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert len(client.get("/api/v1/bookings", headers=who["headers"]).json()["items"]) == 1
    different = book(client, who, start.replace(hour=14), qid=qid, addr=addr, key="req-1")
    assert different.status_code == 409 and different.json()["error"]["code"] == "idempotency_key_reused"


def test_expired_hold_releases_slot(client, db):
    from app.models.bookings import Booking
    make_provider(client)
    a, b = register_customer(client, "a@example.com"), register_customer(client, "b@example.com")
    start = slot(4, 10, weekday=1)
    held = book(client, a, start).json()
    assert book(client, b, start).status_code == 409
    bk = db.get(Booking, uuid.UUID(held["id"]))
    bk.hold_expires_at = utcnow_minus(minutes=1)
    db.commit()
    assert book(client, b, start).status_code == 201
    assert client.get(f"/api/v1/bookings/{held['id']}", headers=a["headers"]).json()["status"] == "expired"
    assert pay(client, a, held["id"]).status_code == 409


def utcnow_minus(minutes):
    from datetime import datetime, timezone
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


def test_booking_validation(client):
    make_provider(client)
    who = register_customer(client)
    assert book(client, who, slot(0, 8) if False else __import__("datetime").datetime.now(LONDON) + timedelta(hours=2)).status_code in (409, 422)
    assert book(client, who, slot(4, 10, 15, weekday=1)).status_code == 422                      # not on the half hour
    assert book(client, who, slot(200, 10)).status_code == 422                                     # beyond horizon
    r = client.post("/api/v1/bookings", headers=who["headers"], json={"quotation_id": quote(client, who)["id"], "address_id": add_address(client, who), "starts_at": slot(4).isoformat(), "accept_terms": False})
    assert r.status_code == 422 and r.json()["error"]["code"] == "terms_required"
    other = add_address(client, who, postcode="SW4 7AB")
    assert book(client, who, slot(4, 10, weekday=1), addr=other).json()["error"]["code"] == "address_mismatch"


def test_preferred_professional(client):
    p1 = make_provider(client, "p1@example.com", name="Pro One")
    p2 = make_provider(client, "p2@example.com", name="Pro Two")
    who = register_customer(client)
    start = slot(4, 10, weekday=1)
    r = book(client, who, start, provider_id=p2["id"])
    assert r.status_code == 201 and r.json()["professional"]["id"] == p2["id"] and r.json()["assignment_mode"] == "chosen"
    # Same professional is not free at the same time for a second request from the same customer.
    clash = book(client, who, start, provider_id=p2["id"])
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "provider_unavailable"
