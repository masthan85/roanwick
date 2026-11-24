from tests.conftest import *  # noqa


def test_registration_validation(client):
    base = {"email": "a@example.com", "full_name": "Anna Lee", "password": PASSWORD, "accept_terms": True}
    assert client.post("/api/v1/auth/register", json={**base, "password": "short"}).status_code == 422
    r = client.post("/api/v1/auth/register", json={**base, "accept_terms": False})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert client.post("/api/v1/auth/register", json=base).status_code == 201
    dup = client.post("/api/v1/auth/register", json=base)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "email_taken"


def test_login_lockout_and_generic_errors(client):
    register_customer(client)
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"email": "priya@example.com", "password": "wrong-password-1"})
        assert r.status_code == 401
    r = client.post("/api/v1/auth/login", json={"email": "priya@example.com", "password": PASSWORD})
    assert r.status_code == 429 and r.json()["error"]["code"] == "account_locked"
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever-1234"})
    assert unknown.status_code == 401 and unknown.json()["error"]["message"] == "Email or password is incorrect."


def test_refresh_rotation_and_reuse_detection(client):
    r = client.post("/api/v1/auth/register", headers={"X-Client": "native"}, json={"email": "n@example.com", "password": PASSWORD, "full_name": "Nina N", "accept_terms": True})
    old = r.json()["refresh_token"]
    assert old
    client.cookies.clear()
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old}, headers={"X-Client": "native"})
    assert r2.status_code == 200 and r2.json()["refresh_token"] != old
    new = r2.json()["refresh_token"]
    client.cookies.clear()
    # Replaying the rotated token is treated as theft and kills the family.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new}).status_code == 401


def test_role_isolation(client):
    c1 = register_customer(client, "one@example.com")
    c2 = register_customer(client, "two@example.com")
    make_provider(client)
    make_staff()
    assert client.get("/api/v1/admin/users", headers=c1["headers"]).status_code == 403
    assert client.get("/api/v1/provider/jobs", headers=c1["headers"]).status_code == 403
    assert client.get("/api/v1/bookings").status_code == 401
    b = confirmed_booking(client, c1)
    assert client.get(f"/api/v1/bookings/{b['id']}", headers=c2["headers"]).status_code == 404
    assert client.post(f"/api/v1/bookings/{b['id']}/cancel", headers=c2["headers"], json={}).status_code == 404
    assert client.get(f"/api/v1/bookings/{b['id']}/messages", headers=c2["headers"]).status_code == 404
    addr = client.get("/api/v1/addresses", headers=c1["headers"]).json()[0]["id"]
    assert client.put(f"/api/v1/addresses/{addr}", headers=c2["headers"], json={"line1": "Hijack Road", "postcode": "SW11 1AB"}).status_code == 404


def test_export_and_erasure(client):
    who = register_customer(client)
    assert client.get("/api/v1/auth/me/export", headers=who["headers"]).json()["account"]["email"] == "priya@example.com"
    assert client.post("/api/v1/auth/me/delete", headers=who["headers"], json={"password": "wrong-password-1"}).status_code == 422
    assert client.post("/api/v1/auth/me/delete", headers=who["headers"], json={"password": PASSWORD}).status_code == 204
    assert client.get("/api/v1/auth/me", headers=who["headers"]).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "priya@example.com", "password": PASSWORD}).status_code == 401


def test_password_reset_flow(client, db):
    from app.core.security import create_purpose_token
    from app.models.identity import User
    from sqlalchemy import select

    who = register_customer(client)
    assert client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}).status_code == 202
    uid = db.scalar(select(User.id).where(User.email == "priya@example.com"))
    token = create_purpose_token(uid, "reset_password", 30)
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Brand-new-pass-1"}).status_code == 204
    assert client.post("/api/v1/auth/login", json={"email": "priya@example.com", "password": "Brand-new-pass-1"}).status_code == 200
    assert client.post("/api/v1/auth/reset-password", json={"token": "garbage", "new_password": "Brand-new-pass-1"}).status_code == 422
