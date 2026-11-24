from tests.conftest import *  # noqa


def test_health_and_catalogue(client):
    assert client.get("/health").json() == {"status": "ok"}
    cats = client.get("/api/v1/catalogue/categories").json()
    assert cats[0]["slug"] == "home-cleaning" and cats[0]["available"]
    assert all(c["coming_soon"] for c in cats[1:])


def test_register_and_book_end_to_end(client):
    make_provider(client)
    who = register_customer(client)
    start = slot(4, 10, weekday=1)
    r = book(client, who, start)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "pending_payment"
    paid = pay(client, who, b["id"])
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "confirmed"
