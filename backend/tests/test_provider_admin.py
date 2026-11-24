import io
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tests.conftest import *  # noqa

PDF = b"%PDF-1.4\n%test\n"


def upload(client, who, doc_type, title="Doc", expires=None, content=PDF, ctype="application/pdf"):
    data = {"doc_type": doc_type, "title": title}
    if expires:
        data["expires_on"] = expires
    return client.post("/api/v1/provider/documents", headers=who["headers"], data=data, files={"file": ("doc.pdf", io.BytesIO(content), ctype)})


def onboard(client, email="newpro@example.com"):
    r = client.post("/api/v1/providers/register", json={"email": email, "password": PASSWORD, "full_name": "Nadia Pro", "phone": "07700900111", "display_name": "Nadia P.", "accept_terms": True})
    assert r.status_code == 201, r.text
    return {"headers": auth(r.json()["access_token"]), "id": r.json()["user"]["id"]}


def complete_profile(client, who):
    oid = offering_id(client)
    h = who["headers"]
    assert client.patch("/api/v1/provider/profile", headers=h, json={"bio": "Five years of domestic cleaning in Battersea and Clapham."}).status_code == 200
    assert client.put("/api/v1/provider/services", headers=h, json={"offering_ids": [oid]}).status_code == 200
    assert client.put("/api/v1/provider/areas", headers=h, json={"outward_codes": ["SW11", "SW12"]}).status_code == 200
    assert client.put("/api/v1/provider/availability", headers=h, json={"rules": [{"weekday": d, "start_time": "08:00", "end_time": "18:00"} for d in range(5)]}).status_code == 200


def test_full_onboarding_and_verification_gate(client):
    make_staff("operations", "ops@roanwick.example")
    ops = login(client, "ops@roanwick.example")
    who = onboard(client)
    customer = register_customer(client)
    start = slot(4, 10, weekday=1)

    assert client.post("/api/v1/provider/submit", headers=who["headers"]).status_code == 422          # checklist incomplete
    complete_profile(client, who)
    far = (date.today() + timedelta(days=400)).isoformat()
    ids = {}
    for t, exp in (("identity", None), ("right_to_work", None), ("public_liability", far)):
        r = upload(client, who, t, t, exp)
        assert r.status_code == 201, r.text
        ids[t] = r.json()["id"]
    assert client.post("/api/v1/provider/submit", headers=who["headers"]).status_code == 200

    # Not yet visible or bookable: documents are unreviewed and the profile is not approved.
    assert client.get(f"/api/v1/professionals/{who['id']}").status_code == 404
    assert book(client, customer, start).status_code == 409

    # Approval is refused until every mandatory document has been approved.
    r = client.post(f"/api/v1/admin/providers/{who['id']}/decision", headers=ops, json={"action": "approve"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "verification_incomplete"
    assert set(r.json()["error"]["details"]["missing"]["home-cleaning"]) == {"identity", "right_to_work", "public_liability"}
    for t in ("identity", "right_to_work"):
        assert client.post(f"/api/v1/admin/documents/{ids[t]}/review", headers=ops, json={"decision": "approve"}).status_code == 200
    r = client.post(f"/api/v1/admin/providers/{who['id']}/decision", headers=ops, json={"action": "approve"})
    assert r.status_code == 422 and r.json()["error"]["details"]["missing"]["home-cleaning"] == ["public_liability"]
    assert client.post(f"/api/v1/admin/documents/{ids['public_liability']}/review", headers=ops, json={"decision": "reject"}).status_code == 422   # reason required
    assert client.post(f"/api/v1/admin/documents/{ids['public_liability']}/review", headers=ops, json={"decision": "approve", "notes": "Policy number checked"}).status_code == 200
    assert client.post(f"/api/v1/admin/providers/{who['id']}/decision", headers=ops, json={"action": "approve"}).status_code == 200

    pub = client.get(f"/api/v1/professionals/{who['id']}").json()
    assert {b["type"] for b in pub["badges"]} == {"identity", "right_to_work", "public_liability"}
    assert "background" not in str(pub).lower()                                 # no unsupported claims
    assert book(client, customer, start).status_code == 201

    audit_rows = client.get("/api/v1/admin/audit", headers=login(client, "ops@roanwick.example")).status_code
    assert audit_rows == 403                                                    # operations cannot read audit logs


def test_expired_insurance_removes_provider_from_availability(client, db):
    from app.models.providers import ProviderDocument
    from sqlalchemy import select
    p = make_provider(client)
    customer = register_customer(client)
    start = slot(4, 10, weekday=1)
    d = start.date().isoformat()
    params = {"offering": "regular-cleaning", "postcode": "SW11 1AB", "minutes": 120, "from_date": d, "days": 1}
    assert client.get("/api/v1/catalogue/slots", params=params).json()["days"]
    doc = db.scalar(select(ProviderDocument).where(ProviderDocument.provider_id == __import__("uuid").UUID(p["id"]), ProviderDocument.doc_type == "public_liability"))
    doc.expires_on = date.today() - timedelta(days=1)
    db.commit()
    assert client.get("/api/v1/catalogue/slots", params=params).json()["days"] == {}
    assert book(client, customer, start).status_code == 409
    alerts = client.get("/api/v1/provider/document-alerts", headers=p["headers"]).json()
    assert alerts and alerts[0]["expired"] is True
    assert client.get(f"/api/v1/professionals/{p['id']}").json()["badges"] and "public_liability" not in {b["type"] for b in client.get(f"/api/v1/professionals/{p['id']}").json()["badges"]}


def test_document_upload_safety(client):
    who = onboard(client)
    assert upload(client, who, "identity", content=b"not a pdf at all").status_code == 422
    assert upload(client, who, "identity", content=b"x" * (5 * 1024 * 1024 + 10)).status_code == 422
    assert upload(client, who, "bogus").status_code == 422
    assert upload(client, who, "public_liability").status_code == 422        # needs an expiry date
    assert upload(client, who, "public_liability", expires=(date.today() - timedelta(days=1)).isoformat()).status_code == 422


def test_provider_cannot_open_unreleased_category(client):
    who = onboard(client)
    from app.models.catalogue import ServiceCategory, ServiceOffering
    from app.core.db import SessionLocal
    with SessionLocal() as s:
        cat = s.query(ServiceCategory).filter_by(slug="gardening").one()
        o = ServiceOffering(category_id=cat.id, slug="lawn", name="Lawn care", pricing_model="hourly", hourly_rate_pence=2500)
        s.add(o)
        s.commit()
        oid = str(o.id)
    r = client.put("/api/v1/provider/services", headers=who["headers"], json={"offering_ids": [oid]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "category_not_open"


def test_regulated_categories_cannot_be_enabled_without_requirements(client):
    make_staff()
    h = login(client, "admin@roanwick.example")
    r = client.patch("/api/v1/admin/categories/gas-heating", headers=h, json={"is_active": True, "confirm_compliance_reviewed": True})
    assert r.status_code == 422 and r.json()["error"]["code"] == "compliance_review_required"
    assert client.put("/api/v1/admin/categories/gas-heating/requirements", headers=h, json={"requirements": [{"document_type": "qualification", "is_mandatory": True}]}).status_code == 200
    assert client.patch("/api/v1/admin/categories/gas-heating", headers=h, json={"is_active": True}).status_code == 422                                  # needs explicit confirmation
    assert client.patch("/api/v1/admin/categories/gas-heating", headers=h, json={"is_active": True, "confirm_compliance_reviewed": True}).status_code == 200
    assert client.put("/api/v1/admin/flags/maintenance_bundles", headers=h, json={"enabled": True}).status_code == 422


def test_staff_permissions_are_enforced_and_audited(client):
    make_staff("super_admin", "admin@roanwick.example")
    make_staff("support", "support@roanwick.example")
    make_staff("finance", "finance@roanwick.example")
    admin, support, fin = (login(client, e) for e in ("admin@roanwick.example", "support@roanwick.example", "finance@roanwick.example"))
    assert client.put("/api/v1/admin/settings/commission_bps", headers=support, json={"value": 3000}).status_code == 403
    assert client.get("/api/v1/admin/reports/finance", headers=support).status_code == 403
    assert client.get("/api/v1/admin/reports/finance", headers=fin).status_code == 200
    assert client.put("/api/v1/admin/settings/commission_bps", headers=fin, json={"value": 3000}).status_code == 403
    assert client.put("/api/v1/admin/settings/commission_bps", headers=admin, json={"value": 99999}).status_code == 422
    assert client.put("/api/v1/admin/settings/commission_bps", headers=admin, json={"value": 2500}).status_code == 200
    log = client.get("/api/v1/admin/audit", headers=admin, params={"action": "setting"}).json()
    assert log["total"] == 1 and log["items"][0]["before"] == {"value": 2200} and log["items"][0]["after"] == {"value": 2500}
    assert log["items"][0]["actor"] == "admin@roanwick.example"
    # Staff accounts are not customers.
    assert client.get("/api/v1/bookings", headers=admin).status_code == 403


def test_admin_manual_assignment_and_cancel(client):
    p1 = make_provider(client, "p1@example.com", name="Pro One", auto_accept=False)
    p2 = make_provider(client, "p2@example.com", name="Pro Two", auto_accept=False)
    make_staff("operations", "ops@roanwick.example")
    ops = login(client, "ops@roanwick.example")
    who = register_customer(client)
    b = confirmed_booking(client, who)
    cands = client.get(f"/api/v1/admin/bookings/{b['id']}/candidates", headers=ops).json()
    target = next(c for c in cands if c["id"] != b["professional"]["id"]) if len(cands) > 1 else None
    other_id = p2["id"] if b["professional"]["id"] == p1["id"] else p1["id"]
    r = client.post(f"/api/v1/admin/bookings/{b['id']}/assign", headers=ops, json={"provider_id": other_id})
    assert r.status_code == 200 and r.json()["provider_id"] == other_id
    assert client.get(f"/api/v1/admin/bookings/{b['id']}", headers=ops).json()["status"] == "awaiting_provider"
    assert client.post(f"/api/v1/admin/bookings/{b['id']}/cancel", headers=ops, json={"reason": "Customer asked by phone"}).status_code == 403   # ops cannot refund
