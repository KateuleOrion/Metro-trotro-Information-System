"""Drivers use the same login as mates and station managers.

New driver: registers (POST /auth/register, role 'driver') -> pending login + driver request ->
the manager approves on the Drivers tab -> driver (and vehicle) created, login switched on.
Existing driver with no login: registers with their phone -> approving links the login.
Sample data: driver Kwame Asare has a login, 0240000001 / driver123, vehicle GT-1234-24 (queue position 1).
Kofi Mensah (0240000002) is a driver with no login yet.
"""


def login(client, who, password):
    return client.post("/auth/login", json={"login": who, "password": password})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


NEW = {"full_name": "Enoch Bwalya", "role": "driver", "phone_number": "+233 26 096 2356", "password": "drive1234",
       "registration_number": "gr-4445-98", "destination": "Madina", "capacity": 14}


def test_existing_driver_logs_in_and_sees_own_vehicle(client):
    r = login(client, "0240000001", "driver123")
    assert r.status_code == 200 and r.json()["role"] == "driver"
    me = client.get("/driver/me", headers=auth(r.json()["token"]))
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["full_name"] == "Kwame Asare"
    v = body["vehicles"][0]
    assert v["registration_number"] == "GT-1234-24" and v["queue_position"] == 1 and v["is_my_turn"] is True
    assert v["available_seats"] == 8 and v["capacity"] == 14


def test_new_driver_registers_and_waits(client, db):
    r = client.post("/auth/register", json=NEW)
    assert r.status_code == 201, r.text
    assert r.json()["account_status"] == "pending"
    req = db.execute("SELECT * FROM driver_requests WHERE request_id = %s", (r.json()["request_id"],)).fetchone()
    assert req["phone_number"] == "0260962356" and req["registration_number"] == "GR-4445-98"
    assert req["account_id"] == r.json()["staff_id"]
    r = login(client, "0260962356", "drive1234")
    assert r.status_code == 403 and "waiting" in r.json()["detail"]


def test_manager_approval_switches_login_on_and_creates_vehicle(client, manager):
    rid = client.post("/auth/register", json=NEW).json()["request_id"]
    pending = client.get("/driver/requests", headers=manager).json()
    assert any(x["request_id"] == rid and x["account_id"] for x in pending)
    assert client.post(f"/driver/requests/{rid}/approve", headers=manager).status_code == 200
    token = login(client, "0260962356", "drive1234").json()["token"]
    me = client.get("/driver/me", headers=auth(token)).json()
    assert me["full_name"] == "Enoch Bwalya"
    assert me["vehicles"][0]["registration_number"] == "GR-4445-98" and me["vehicles"][0]["in_queue"] is False


def test_driver_logins_are_not_in_the_accounts_tab(client, manager):
    sid = client.post("/auth/register", json=NEW).json()["staff_id"]
    assert all(a["role"] != "driver" for a in client.get("/staff/accounts", headers=manager).json())
    r = client.post(f"/staff/accounts/{sid}/approve", headers=manager)
    assert r.status_code == 409 and "Drivers tab" in r.json()["detail"]


def test_rejected_driver_cannot_log_in_but_can_register_again(client, manager):
    rid = client.post("/auth/register", json=NEW).json()["request_id"]
    client.post(f"/driver/requests/{rid}/reject", headers=manager, json={"reason": "Bring your licence"})
    r = login(client, "0260962356", "drive1234")
    assert r.status_code == 403 and "not approved" in r.json()["detail"]
    r = client.post("/auth/register", json={**NEW, "password": "newpass99"})
    assert r.status_code == 201 and r.json()["account_status"] == "pending"
    client.post(f"/driver/requests/{r.json()['request_id']}/approve", headers=manager)
    assert login(client, "0260962356", "newpass99").status_code == 200


def test_existing_driver_without_login_registers_and_is_linked(client, manager, db):
    r = client.post("/auth/register", json={"full_name": "Kofi Mensah", "role": "driver",
                                            "phone_number": "0240000002", "password": "kofi12345"})
    assert r.status_code == 201
    client.post(f"/driver/requests/{r.json()['request_id']}/approve", headers=manager)
    assert db.execute("SELECT COUNT(*) AS n FROM drivers").fetchone()["n"] == 3          # no duplicate driver
    me = client.get("/driver/me", headers=auth(login(client, "0240000002", "kofi12345").json()["token"])).json()
    assert me["driver_id"] == 2 and me["vehicles"][0]["registration_number"] == "GT-5678-24"


def test_driver_with_a_login_cannot_register_again(client):
    r = client.post("/auth/register", json={**NEW, "phone_number": "0240000001"})
    assert r.status_code == 409 and "already has an account" in r.json()["detail"]


def test_driver_registration_rules(client):
    assert client.post("/auth/register", json={**NEW, "phone_number": None, "email": "e@x.com"}).status_code == 422
    assert client.post("/auth/register", json={**NEW, "capacity": None}).status_code == 422
    r = client.post("/auth/register", json={"full_name": "Ama", "role": "mate", "phone_number": "0244000111",
                                            "password": "matepass1", "registration_number": "X-1-24",
                                            "destination": "Tema", "capacity": 10})
    assert r.status_code == 422 and "Only drivers" in r.json()["detail"]
    assert client.post("/auth/register", json={**NEW, "registration_number": "GT-1234-24"}).status_code == 409


def test_driver_cannot_use_other_apps(client):
    h = auth(login(client, "0240000001", "driver123").json()["token"])
    for method, path, body in [("get", "/vehicles", None), ("post", "/vehicles/1/book-seats", {"count": 1}),
                               ("post", "/queue/departures", {"vehicle_id": 1}), ("get", "/driver/requests", None)]:
        r = getattr(client, method)(path, headers=h, **({"json": body} if body else {}))
        assert r.status_code == 403 and r.json()["detail"] == "Drivers can only see their own vehicles", path


def test_only_drivers_open_the_driver_app(client, staff):
    r = client.get("/driver/me", headers=staff)
    assert r.status_code == 403 and "Only drivers" in r.json()["detail"]
    mate = auth(login(client, "0200000004", "mate123").json()["token"])
    assert client.get("/driver/me", headers=mate).status_code == 403


# ------------------------------------------------------------------ the driver's map
def test_driver_map_shows_destination_and_station(client):
    me = client.get("/driver/me", headers=auth(login(client, "0240000001", "driver123").json()["token"])).json()
    m = me["vehicles"][0]["map"]
    assert m["destination"] == "Madina" and m["destination_latitude"] == 5.6693
    assert me["station"]["name"] == "Metro Central Station" and me["station"]["latitude"] == 5.5465


def test_driver_shares_location_of_own_vehicle_only(client):
    h = auth(login(client, "0240000001", "driver123").json()["token"])
    r = client.post("/tracking/position", headers=h, json={"vehicle_id": 1, "latitude": 5.60, "longitude": -0.19})
    assert r.status_code == 201, r.text
    m = client.get("/driver/me", headers=h).json()["vehicles"][0]["map"]
    assert m["latitude"] == 5.6 and m["distance_km"] > 0 and m["stale"] is False
    r = client.post("/tracking/position", headers=h, json={"vehicle_id": 2, "latitude": 5.60, "longitude": -0.19})
    assert r.status_code == 403 and "own vehicle" in r.json()["detail"]
