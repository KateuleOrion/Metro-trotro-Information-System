"""Mates (conductors) have their own app: their own login, and they may only book and cancel seats.

Sample data: mate Kofi Boateng, 0200000004 / mate123. Vehicle 1 has 8 of 14 seats free.
"""


def mate_headers(client):
    r = client.post("/auth/login", json={"login": "0200000004", "password": "mate123"})
    assert r.status_code == 200 and r.json()["role"] == "mate"
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_mate_can_see_vehicles_and_book_seats(client):
    h = mate_headers(client)
    assert client.get("/vehicles", headers=h).status_code == 200
    assert client.get("/auth/me", headers=h).json()["role"] == "mate"
    r = client.post("/vehicles/1/book-seats", headers=h, json={"count": 2})
    assert r.status_code == 200 and r.json()["available_seats"] == 6
    assert client.post("/vehicles/1/release-seats", headers=h, json={"count": 1}).json()["available_seats"] == 7


def test_mate_cannot_use_staff_features(client):
    h = mate_headers(client)
    for method, path, body in [
        ("post", "/queue/arrivals", {"vehicle_id": 3}),
        ("post", "/queue/departures", {"vehicle_id": 1}),
        ("put", "/vehicles/1", {"available_seats": 14}),
        ("post", "/vehicles", {"registration_number": "AB-1-24", "route_id": 1, "capacity": 14}),
        ("get", "/trips", None),
        ("get", "/driver/requests", None),
        ("get", "/staff/accounts", None),
    ]:
        r = getattr(client, method)(path, headers=h, **({"json": body} if body else {}))
        assert r.status_code == 403, (method, path, r.status_code)
        assert r.json()["detail"] == "Mates can only book and cancel seats"


def test_mate_registers_and_waits_for_approval(client, manager):
    r = client.post("/auth/register", json={"full_name": "Yaw Mensah", "role": "mate",
                                            "phone_number": "0244777888", "password": "matepass1"})
    assert r.status_code == 201 and r.json()["account_status"] == "pending"
    assert client.post("/auth/login", json={"login": "0244777888", "password": "matepass1"}).status_code == 403
    waiting = client.get("/staff/accounts", headers=manager).json()
    assert any(a["full_name"] == "Yaw Mensah" and a["role"] == "mate" for a in waiting)
    client.post(f"/staff/accounts/{r.json()['staff_id']}/approve", headers=manager)
    assert client.post("/auth/login", json={"login": "0244777888", "password": "matepass1"}).json()["role"] == "mate"
