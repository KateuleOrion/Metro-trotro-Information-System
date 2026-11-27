"""Tests for driver registration requests: a driver asks to be registered, the station manager
approves or rejects.

Sample data (metro_trotro_db.sql): request 1 (Kojo Antwi, with vehicle GW-2201-25 to Madina) and
request 2 (Akosua Darko, no vehicle) are pending. Drivers 1-3 exist; Kofi Mensah's phone is 0240000002.
"""


def count(db, table, where="TRUE"):
    return db.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}").fetchone()["n"]


NEW = {"full_name": "Efua Sarpong", "phone_number": "0277770001"}
NEW_WITH_VEHICLE = {**NEW, "registration_number": "gw-3300-25", "destination": "Tema", "capacity": 18}


# ------------------------------------------------------------------ driver sends a request
def test_driver_can_send_a_request_without_signing_in(client, db):
    r = client.post("/driver/requests", json=NEW_WITH_VEHICLE)
    assert r.status_code == 201, r.text
    assert r.json()["request_status"] == "pending"
    row = db.execute("SELECT * FROM driver_requests WHERE request_id = %s", (r.json()["request_id"],)).fetchone()
    assert row["registration_number"] == "GW-3300-25"      # stored in capitals
    assert count(db, "drivers") == 3                       # nobody is registered yet


def test_vehicle_details_must_be_complete(client):
    r = client.post("/driver/requests", json={**NEW, "registration_number": "GW-1-25"})
    assert r.status_code == 422 and "registration number, destination and number of seats" in r.json()["detail"]


def test_bad_phone_and_missing_name_are_rejected(client):
    assert client.post("/driver/requests", json={**NEW, "phone_number": "abc"}).status_code == 422
    assert client.post("/driver/requests", json={"phone_number": "0277770001"}).status_code == 422


def test_only_one_waiting_request_per_phone(client):
    assert client.post("/driver/requests", json=NEW).status_code == 201
    r = client.post("/driver/requests", json={**NEW, "full_name": "Efua S."})
    assert r.status_code == 409 and "already have a request waiting" in r.json()["detail"]


def test_registered_driver_cannot_request_again(client):
    r = client.post("/driver/requests", json={"full_name": "Kofi Mensah", "phone_number": "0240000002"})
    assert r.status_code == 409 and "already registered" in r.json()["detail"]


def test_registered_plate_cannot_be_requested(client):
    r = client.post("/driver/requests", json={**NEW_WITH_VEHICLE, "registration_number": "gt-1234-24"})
    assert r.status_code == 409


def test_driver_can_check_status_by_phone(client):
    client.post("/driver/requests", json=NEW)
    r = client.get("/driver/requests/status", params={"phone": "0277770001"})
    assert r.status_code == 200 and r.json()["request_status"] == "pending"
    assert "full_name" not in r.json()                     # no personal details from a phone number
    assert client.get("/driver/requests/status", params={"phone": "0200000000"}).status_code == 404


# ------------------------------------------------------------------ station manager reviews
def test_only_manager_can_see_and_review_requests(client, staff):
    assert client.get("/driver/requests").status_code == 401
    assert client.get("/driver/requests", headers=staff).status_code == 403
    assert client.post("/driver/requests/1/approve", headers=staff).status_code == 403
    assert client.post("/driver/requests/1/reject", headers=staff, json={}).status_code == 403


def test_manager_sees_waiting_requests_oldest_first(client, manager):
    r = client.get("/driver/requests", headers=manager)
    assert r.status_code == 200
    assert [x["request_id"] for x in r.json()] == [1, 2]
    assert client.get("/driver/requests?status=approved", headers=manager).json() == []


def test_approving_creates_driver_and_vehicle(client, manager, db):
    r = client.post("/driver/requests/1/approve", headers=manager)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["request_status"] == "approved" and body["reviewed_by_name"] == "Demo Station Manager"
    driver = db.execute("SELECT * FROM drivers WHERE driver_id = %s", (body["driver_id"],)).fetchone()
    assert driver["driver_name"] == "Kojo Antwi" and driver["phone_number"] == "0245550101"
    vehicles = client.get("/vehicles", headers=manager).json()["vehicles"]
    v = next(x for x in vehicles if x["vehicle_id"] == body["vehicle_id"])
    assert v["registration_number"] == "GW-2201-25" and v["driver_name"] == "Kojo Antwi"
    assert v["route_id"] == 1 and v["capacity"] == 14 and v["available_seats"] == 14
    assert count(db, "audit_log", "action = 'DRIVER_REQUEST_APPROVED'") == 1


def test_approving_without_vehicle_creates_only_the_driver(client, manager, db):
    r = client.post("/driver/requests/2/approve", headers=manager)
    assert r.status_code == 200 and r.json()["vehicle_id"] is None
    assert count(db, "drivers") == 4 and count(db, "vehicles") == 3
    # the new driver can now be chosen for a vehicle
    names = [d["driver_name"] for d in client.get("/drivers", headers=manager).json()]
    assert "Akosua Darko" in names


def test_new_destination_in_request_creates_a_route_on_approval(client, manager, db):
    rid = client.post("/driver/requests", json=NEW_WITH_VEHICLE).json()["request_id"]
    assert count(db, "routes") == 3
    assert client.post(f"/driver/requests/{rid}/approve", headers=manager).status_code == 200
    assert count(db, "routes") == 4


def test_rejecting_keeps_the_reason_and_creates_nothing(client, manager, db):
    r = client.post("/driver/requests/1/reject", headers=manager, json={"reason": "Vehicle papers not shown"})
    assert r.status_code == 200 and r.json()["request_status"] == "rejected"
    assert count(db, "drivers") == 3 and count(db, "vehicles") == 3
    s = client.get("/driver/requests/status", params={"phone": "0245550101"}).json()
    assert s["request_status"] == "rejected" and s["reject_reason"] == "Vehicle papers not shown"


def test_driver_can_send_a_new_request_after_rejection(client, manager):
    client.post("/driver/requests/2/reject", headers=manager, json={})
    r = client.post("/driver/requests", json={"full_name": "Akosua Darko", "phone_number": "0205550202"})
    assert r.status_code == 201


def test_a_request_cannot_be_reviewed_twice(client, manager):
    assert client.post("/driver/requests/1/approve", headers=manager).status_code == 200
    assert client.post("/driver/requests/1/approve", headers=manager).status_code == 409
    assert client.post("/driver/requests/1/reject", headers=manager, json={}).status_code == 409
    assert client.post("/driver/requests/999/approve", headers=manager).status_code == 404


def test_approval_is_refused_if_plate_was_taken_meanwhile(client, manager, db):
    # Someone added the same vehicle after the request was sent.
    client.post("/vehicles", headers=manager, json={"registration_number": "GW-2201-25", "capacity": 14, "route_id": 1})
    r = client.post("/driver/requests/1/approve", headers=manager)
    assert r.status_code == 409 and "Reject this request" in r.json()["detail"]
    assert count(db, "drivers") == 3                       # nothing half-saved
    assert db.execute("SELECT request_status FROM driver_requests WHERE request_id = 1").fetchone()["request_status"] == "pending"


# ------------------------------------------------------------------ driver app: login with phone number only
def test_existing_driver_logs_in_with_phone_only(client):
    r = client.post("/driver/login", json={"phone_number": "0240000001"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["full_name"] == "Kwame Asare" and body["driver_id"] == 1
    assert [v["registration_number"] for v in body["vehicles"]] == ["GT-1234-24"]
    assert body["vehicles"][0]["destination"] == "Madina"


def test_driver_login_accepts_phone_written_differently(client):
    assert client.post("/driver/login", json={"phone_number": "+233 24 000 0001"}).status_code == 200


def test_unknown_phone_is_told_to_sign_up(client):
    r = client.post("/driver/login", json={"phone_number": "0277770001"})
    assert r.status_code == 404 and "Please sign up" in r.json()["detail"]
    assert client.post("/driver/login", json={"phone_number": "abc"}).status_code == 422


def test_waiting_driver_cannot_log_in_yet(client):
    r = client.post("/driver/login", json={"phone_number": "0245550101"})  # sample request 1, pending
    assert r.status_code == 403 and "waiting" in r.json()["detail"]


def test_driver_logs_in_after_approval(client, manager):
    client.post("/driver/requests/1/approve", headers=manager)
    r = client.post("/driver/login", json={"phone_number": "0245550101"})
    assert r.status_code == 200 and r.json()["vehicles"][0]["registration_number"] == "GW-2201-25"


def test_rejected_driver_sees_reason(client, manager):
    client.post("/driver/requests/2/reject", headers=manager, json={"reason": "Bring your licence"})
    r = client.post("/driver/login", json={"phone_number": "0205550202"})
    assert r.status_code == 403 and "Bring your licence" in r.json()["detail"]


def test_signup_with_plus233_then_login_with_local_number(client, manager):
    rid = client.post("/driver/requests", json={"full_name": "Efua Sarpong", "phone_number": "+233 27 777 0001"}).json()["request_id"]
    assert client.get("/driver/requests/status", params={"phone": "0277770001"}).json()["request_id"] == rid
    client.post(f"/driver/requests/{rid}/approve", headers=manager)
    assert client.post("/driver/login", json={"phone_number": "0277770001"}).json()["full_name"] == "Efua Sarpong"
