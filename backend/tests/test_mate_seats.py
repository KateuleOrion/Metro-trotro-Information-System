"""Tests for the mate / conductor seat booking (book-seats and release-seats).

Sample data: vehicle 1 (GT-1234-24) has 14 seats with 8 free.
"""


def seats(client, staff, vid=1):
    return next(v for v in client.get("/vehicles", headers=staff).json()["vehicles"] if v["vehicle_id"] == vid)["available_seats"]


def test_book_and_release_seats(client, staff):
    r = client.post("/vehicles/1/book-seats", headers=staff, json={"count": 3})
    assert r.status_code == 200 and r.json()["available_seats"] == 5
    r = client.post("/vehicles/1/release-seats", headers=staff, json={"count": 2})
    assert r.status_code == 200 and r.json()["available_seats"] == 7


def test_cannot_book_more_than_seats_left(client, staff):
    r = client.post("/vehicles/1/book-seats", headers=staff, json={"count": 9})
    assert r.status_code == 409 and "Only 8 seats left" in r.json()["detail"]
    assert seats(client, staff) == 8


def test_full_vehicle(client, staff):
    client.post("/vehicles/1/book-seats", headers=staff, json={"count": 8})
    r = client.post("/vehicles/1/book-seats", headers=staff, json={"count": 1})
    assert r.status_code == 409 and "full" in r.json()["detail"]


def test_cannot_cancel_more_than_booked(client, staff):
    r = client.post("/vehicles/1/release-seats", headers=staff, json={"count": 7})
    assert r.status_code == 409 and "Only 6 passengers are booked" in r.json()["detail"]


def test_bad_count_and_sign_in_needed(client, staff):
    assert client.post("/vehicles/1/book-seats", headers=staff, json={"count": 0}).status_code == 422
    assert client.post("/vehicles/1/book-seats", json={"count": 1}).status_code == 401
    assert client.post("/vehicles/999/book-seats", headers=staff, json={"count": 1}).status_code == 404


def test_unavailable_vehicle_cannot_be_booked(client, staff):
    client.post("/queue/cancel", headers=staff, json={"vehicle_id": 1})
    client.put("/vehicles/1", headers=staff, json={"vehicle_status": "unavailable"})
    r = client.post("/vehicles/1/book-seats", headers=staff, json={"count": 1})
    assert r.status_code == 409 and "unavailable" in r.json()["detail"]
