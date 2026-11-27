"""Automated tests for the Metro Trotro API. Each test starts from the sample data in metro_trotro_db.sql:

  vehicles : 1 GT-1234-24 (route 1, queue #1, waiting, 8 seats free)
             2 GT-5678-24 (route 2, queue #2, loading, 3 seats free)
             3 GT-9012-24 (route 3, not in queue, 14 seats free, one departure 45 min ago)
  staff    : demo@station.com / demo123 (station manager), ama@station.com / staff123 (station staff)
"""
import uuid
from datetime import datetime, timedelta, timezone


def iso(minutes_ago=0):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def queue_plates(client):
    return [q["vehicle"]["registration_number"] for q in client.get("/queue").json()["queue"]]


# ============================================================ FR14 sign-in and access
def test_login_success_returns_token_and_role(client):
    r = client.post("/auth/login", json={"email": "demo@station.com", "password": "demo123"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "station_manager" and body["token"] and body["name"]


def test_login_wrong_password_rejected(client):
    r = client.post("/auth/login", json={"email": "demo@station.com", "password": "wrong"})
    assert r.status_code == 401 and r.json()["detail"] == "Wrong phone number, email or password"


def test_login_unknown_email_gives_same_message(client):
    r = client.post("/auth/login", json={"email": "nobody@station.com", "password": "x"})
    assert r.status_code == 401 and r.json()["detail"] == "Wrong phone number, email or password"


def test_login_email_is_not_case_sensitive(client):
    r = client.post("/auth/login", json={"email": "  DEMO@Station.com ", "password": "demo123"})
    assert r.status_code == 200


def test_plain_text_sample_password_is_rehashed_after_login(client, db):
    client.post("/auth/login", json={"email": "demo@station.com", "password": "demo123"})
    stored = db.execute("SELECT password_hash FROM staff WHERE email = 'demo@station.com'").fetchone()["password_hash"]
    assert stored.startswith("$2") and stored != "demo123"
    # and the password still works afterwards
    assert client.post("/auth/login", json={"email": "demo@station.com", "password": "demo123"}).status_code == 200


def test_too_many_wrong_passwords_locks_sign_in_briefly(client):
    for _ in range(5):
        assert client.post("/auth/login", json={"email": "ama@station.com", "password": "bad"}).status_code == 401
    r = client.post("/auth/login", json={"email": "ama@station.com", "password": "staff123"})
    assert r.status_code == 429


def test_inactive_account_cannot_sign_in(client, db):
    db.execute("UPDATE staff SET account_status = 'inactive' WHERE email = 'ama@station.com'")
    r = client.post("/auth/login", json={"email": "ama@station.com", "password": "staff123"})
    assert r.status_code == 403


def test_editing_requires_sign_in(client):
    assert client.post("/queue/arrivals", json={"vehicle_id": 3}).status_code == 401
    assert client.put("/queue/order", json={"vehicle_ids": [2, 1]}).status_code == 401
    assert client.post("/queue/departures", json={"vehicle_id": 1}).status_code == 401
    assert client.post("/vehicles", json={"registration_number": "X", "route_id": 1, "capacity": 5}).status_code == 401
    assert client.get("/vehicles").status_code == 401
    assert client.get("/trips").status_code == 401
    assert client.get("/drivers").status_code == 401


def test_bad_or_tampered_token_rejected(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_me_returns_current_staff(client, staff):
    r = client.get("/auth/me", headers=staff)
    assert r.json()["role"] == "station_staff"


def test_deactivated_staff_token_stops_working(client, staff, db):
    db.execute("UPDATE staff SET account_status = 'inactive' WHERE email = 'ama@station.com'")
    assert client.get("/auth/me", headers=staff).status_code == 401


def test_only_manager_can_add_vehicles_approve_drivers_and_add_routes(client, staff):
    assert client.post("/vehicles", headers=staff, json={"registration_number": "AB-1-24", "route_id": 1, "capacity": 14}).status_code == 403
    assert client.post("/driver/requests/1/approve", headers=staff).status_code == 403
    assert client.post("/routes", headers=staff, json={"destination": "Tema"}).status_code == 403
    assert client.get("/activity", headers=staff).status_code == 403


# ============================================================ public passenger information
def test_queue_is_public_and_ordered(client):
    r = client.get("/queue")
    assert r.status_code == 200
    assert queue_plates(client) == ["GT-1234-24", "GT-5678-24"]
    first = r.json()["queue"][0]
    assert first["position"] == 1 and first["vehicle"]["available_seats"] == 8
    assert "driver_name" not in first["vehicle"] and "phone_number" not in str(r.json())  # privacy


def test_routes_are_public(client):
    names = [r["route_name"] for r in client.get("/routes").json()]
    assert "Central - Madina" in names and len(names) == 3


def test_passenger_search_finds_route_and_queued_vehicles(client):
    r = client.get("/passenger/search", params={"to": "madina"}).json()
    assert len(r["results"]) == 1
    res = r["results"][0]
    assert res["route"]["destination"] == "Madina"
    assert [v["registration_number"] for v in res["vehicles"]] == ["GT-1234-24"]
    assert res["vehicles"][0]["available_seats"] == 8
    assert res["vehicles"][0]["status_label"] == "Waiting in queue"
    assert res["fare"] is None  # fares are not stored yet: the app must show "Unavailable"


def test_passenger_search_partial_text_and_case(client):
    assert len(client.get("/passenger/search", params={"to": "KAS"}).json()["results"]) == 1


def test_passenger_search_no_match_returns_empty_list(client):
    r = client.get("/passenger/search", params={"to": "Timbuktu"})
    assert r.status_code == 200 and r.json()["results"] == []


def test_passenger_search_blank_lists_every_route(client):
    assert len(client.get("/passenger/search").json()["results"]) == 3


def test_search_text_with_special_characters_is_safe(client):
    r = client.get("/passenger/search", params={"to": "%' OR 1=1 --"})
    assert r.status_code == 200 and r.json()["results"] == []
    r = client.get("/passenger/search", params={"to": "%"})
    assert r.status_code == 200 and r.json()["results"] == []  # '%' is matched literally


def test_wait_time_is_unavailable_with_fewer_than_two_departures(client):
    res = client.get("/passenger/search", params={"to": "madina"}).json()["results"][0]
    assert res["estimated_wait_minutes"] is None  # no departures recorded for route 1


def test_wait_time_appears_and_changes_when_departures_are_recorded(client, staff, db):
    db.execute("INSERT INTO departures (vehicle_id, route_id, station_id, departure_time) "
               "VALUES (1, 1, 1, CURRENT_TIMESTAMP - INTERVAL '30 minutes'), "
               "(1, 1, 1, CURRENT_TIMESTAMP - INTERVAL '10 minutes')")
    res = client.get("/passenger/search", params={"to": "madina"}).json()["results"][0]
    assert res["wait_basis_departures"] == 2
    before = res["estimated_wait_minutes"]
    assert before is not None and 8 <= before <= 12  # average gap 20 min, 10 min since the last one

    # Record a departure now; the vehicle then comes back, so there is something to wait for.
    assert client.post("/queue/departures", headers=staff, json={"vehicle_id": 1}).status_code == 201
    assert client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 1}).status_code == 201
    after = client.get("/passenger/search", params={"to": "madina"}).json()["results"][0]["estimated_wait_minutes"]
    assert after is not None and after != before  # gaps are now 20 and 10, so the estimate moved to about 15


def test_wait_time_is_unavailable_when_no_vehicle_is_waiting(client, staff, db):
    db.execute("INSERT INTO departures (vehicle_id, route_id, station_id, departure_time) "
               "VALUES (3, 3, 1, CURRENT_TIMESTAMP - INTERVAL '5 minutes')")
    res = client.get("/passenger/search", params={"to": "kasoa"}).json()["results"][0]
    assert res["vehicles"] == [] and res["estimated_wait_minutes"] is None


def test_search_stays_up_to_date_with_departures(client, staff):
    client.post("/queue/departures", headers=staff, json={"vehicle_id": 1})
    res = client.get("/passenger/search", params={"to": "madina"}).json()["results"][0]
    assert res["vehicles"] == [] and res["last_departure"] is not None


# ============================================================ driver turn (FR19)
def test_driver_sees_it_is_their_turn_when_first(client):
    r = client.get("/driver/turn", params={"vehicle_id": 1}).json()
    assert r["in_queue"] and r["is_my_turn"] and r["vehicles_ahead"] == 0


def test_driver_sees_vehicles_ahead(client):
    r = client.get("/driver/turn", params={"registration_number": "gt-5678-24"}).json()
    assert not r["is_my_turn"] and r["vehicles_ahead"] == 1 and r["queue_position"] == 2


def test_driver_not_in_queue(client):
    r = client.get("/driver/turn", params={"vehicle_id": 3}).json()
    assert r["in_queue"] is False and r["is_my_turn"] is False and r["queue_position"] is None


def test_driver_turn_changes_when_queue_changes(client, staff):
    assert client.get("/driver/turn", params={"vehicle_id": 2}).json()["is_my_turn"] is False
    client.post("/queue/departures", headers=staff, json={"vehicle_id": 1})
    assert client.get("/driver/turn", params={"vehicle_id": 2}).json()["is_my_turn"] is True


def test_driver_unknown_vehicle_and_missing_parameter(client):
    assert client.get("/driver/turn", params={"vehicle_id": 999}).status_code == 404
    assert client.get("/driver/turn").status_code == 422


def test_driver_vehicle_list_has_no_personal_details(client):
    r = client.get("/driver/vehicles")
    assert r.status_code == 200 and len(r.json()) == 3
    assert "driver_name" not in str(r.json())


# ============================================================ FR7, FR8, FR10 queue
def test_record_arrival_adds_to_end_of_queue(client, staff):
    r = client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 3})
    assert r.status_code == 201 and r.json()["queue_position"] == 3
    assert queue_plates(client)[-1] == "GT-9012-24"
    vehicles = {v["vehicle_id"]: v for v in client.get("/vehicles", headers=staff).json()["vehicles"]}
    assert vehicles[3]["vehicle_status"] == "queued" and vehicles[3]["in_queue"] is True


def test_cannot_record_arrival_twice(client, staff):
    r = client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 1})
    assert r.status_code == 409 and "already in the queue" in r.json()["detail"]


def test_arrival_unknown_vehicle(client, staff):
    assert client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 999}).status_code == 404


def test_unavailable_vehicle_cannot_arrive(client, staff):
    client.put("/vehicles/3", headers=staff, json={"vehicle_status": "unavailable"})
    assert client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 3}).status_code == 409


def test_reorder_queue(client, staff):
    r = client.put("/queue/order", headers=staff, json={"vehicle_ids": [2, 1]})
    assert r.status_code == 200
    assert queue_plates(client) == ["GT-5678-24", "GT-1234-24"]
    assert [q["position"] for q in client.get("/queue").json()["queue"]] == [1, 2]


def test_reorder_three_vehicles(client, staff):
    client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 3})
    client.put("/queue/order", headers=staff, json={"vehicle_ids": [3, 1, 2]})
    assert queue_plates(client) == ["GT-9012-24", "GT-1234-24", "GT-5678-24"]


def test_reorder_rejects_wrong_or_duplicate_vehicles(client, staff):
    assert client.put("/queue/order", headers=staff, json={"vehicle_ids": [1]}).status_code == 409
    assert client.put("/queue/order", headers=staff, json={"vehicle_ids": [1, 1]}).status_code == 409
    assert client.put("/queue/order", headers=staff, json={"vehicle_ids": [1, 3]}).status_code == 409
    assert queue_plates(client) == ["GT-1234-24", "GT-5678-24"]  # unchanged


def test_departure_removes_vehicle_closes_gap_and_records_trip(client, staff):
    r = client.post("/queue/departures", headers=staff, json={"vehicle_id": 1})
    assert r.status_code == 201
    q = client.get("/queue").json()["queue"]
    assert [(x["vehicle"]["registration_number"], x["position"]) for x in q] == [("GT-5678-24", 1)]
    trips = client.get("/trips", headers=staff).json()["trips"]
    assert trips[0]["registration_number"] == "GT-1234-24"
    vehicles = {v["vehicle_id"]: v for v in client.get("/vehicles", headers=staff).json()["vehicles"]}
    assert vehicles[1]["vehicle_status"] == "departed" and vehicles[1]["in_queue"] is False


def test_departure_from_the_middle_keeps_order(client, staff):
    client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 3})
    client.post("/queue/departures", headers=staff, json={"vehicle_id": 2})
    assert queue_plates(client) == ["GT-1234-24", "GT-9012-24"]
    assert [q["position"] for q in client.get("/queue").json()["queue"]] == [1, 2]


def test_departure_when_not_in_queue(client, staff):
    r = client.post("/queue/departures", headers=staff, json={"vehicle_id": 3})
    assert r.status_code == 409 and "not in the queue" in r.json()["detail"]


def test_vehicle_can_rejoin_queue_after_departure(client, staff):
    client.post("/queue/departures", headers=staff, json={"vehicle_id": 1})
    r = client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 1})
    assert r.status_code == 201 and r.json()["queue_position"] == 2


def test_remove_vehicle_from_queue(client, staff):
    assert client.post("/queue/cancel", headers=staff, json={"vehicle_id": 1}).status_code == 200
    assert queue_plates(client) == ["GT-5678-24"]
    vehicles = {v["vehicle_id"]: v for v in client.get("/vehicles", headers=staff).json()["vehicles"]}
    assert vehicles[1]["vehicle_status"] == "available"
    assert client.post("/queue/cancel", headers=staff, json={"vehicle_id": 1}).status_code == 409


# ============================================================ FR2, FR3, FR9 vehicles and seats
def test_list_vehicles_shows_seats_driver_and_route(client, staff):
    r = client.get("/vehicles", headers=staff).json()
    v1 = next(v for v in r["vehicles"] if v["vehicle_id"] == 1)
    assert v1["available_seats"] == 8 and v1["capacity"] == 14
    assert v1["driver_name"] == "Kwame Asare" and v1["route_name"] == "Central - Madina"


def test_manager_adds_vehicle_with_default_seats(client, manager):
    r = client.post("/vehicles", headers=manager,
                    json={"registration_number": " gr 7777-24 ", "route_id": 1, "capacity": 15, "driver_id": 2})
    assert r.status_code == 201
    v = r.json()
    assert v["registration_number"] == "GR 7777-24" and v["available_seats"] == 15
    assert v["vehicle_status"] == "available" and v["in_queue"] is False


def test_duplicate_registration_rejected(client, manager):
    r = client.post("/vehicles", headers=manager, json={"registration_number": "GT-1234-24", "route_id": 1, "capacity": 14})
    assert r.status_code == 409 and "already exists" in r.json()["detail"]


def test_add_vehicle_validation_messages(client, manager):
    r = client.post("/vehicles", headers=manager, json={"registration_number": "", "route_id": 1, "capacity": 14})
    assert r.status_code == 422 and "registration_number" in r.json()["detail"]
    r = client.post("/vehicles", headers=manager, json={"registration_number": "A-1", "route_id": 1, "capacity": 0})
    assert r.status_code == 422 and "capacity" in r.json()["detail"]
    r = client.post("/vehicles", headers=manager, json={"registration_number": "A-1", "route_id": 1, "capacity": "abc"})
    assert r.status_code == 422
    r = client.post("/vehicles", headers=manager, json={"registration_number": "A-1", "route_id": 999, "capacity": 14})
    assert r.status_code == 422 and "route" in r.json()["detail"].lower()
    r = client.post("/vehicles", headers=manager,
                    json={"registration_number": "A-1", "route_id": 1, "capacity": 14, "available_seats": 20})
    assert r.status_code == 422 and "capacity" in r.json()["detail"]


def test_staff_updates_seats_and_history_is_kept(client, staff, db):
    r = client.put("/vehicles/1", headers=staff, json={"available_seats": 2})
    assert r.status_code == 200 and r.json()["available_seats"] == 2
    assert db.execute("SELECT COUNT(*) AS n FROM seat_availability WHERE vehicle_id = 1").fetchone()["n"] == 2


def test_seats_cannot_exceed_capacity_or_be_negative(client, staff):
    assert client.put("/vehicles/1", headers=staff, json={"available_seats": 15}).status_code == 422
    assert client.put("/vehicles/1", headers=staff, json={"available_seats": -1}).status_code == 422


def test_zero_seats_is_allowed(client, staff):
    r = client.put("/vehicles/1", headers=staff, json={"available_seats": 0})
    assert r.status_code == 200 and r.json()["available_seats"] == 0


def test_status_changes_follow_queue_rules(client, staff):
    assert client.put("/vehicles/1", headers=staff, json={"vehicle_status": "loading"}).status_code == 200
    assert client.get("/queue").json()["queue"][0]["queue_status"] == "loading"
    assert client.put("/vehicles/1", headers=staff, json={"vehicle_status": "queued"}).status_code == 200
    assert client.get("/queue").json()["queue"][0]["queue_status"] == "waiting"
    # cannot say 'loading' for a vehicle that is not queued, or 'available' while queued
    assert client.put("/vehicles/3", headers=staff, json={"vehicle_status": "loading"}).status_code == 409
    assert client.put("/vehicles/1", headers=staff, json={"vehicle_status": "available"}).status_code == 409
    # 'departed' only through the departure action
    assert client.put("/vehicles/1", headers=staff, json={"vehicle_status": "departed"}).status_code == 409
    assert client.put("/vehicles/1", headers=staff, json={"vehicle_status": "flying"}).status_code == 422


def test_marking_unavailable_removes_it_from_the_queue(client, staff):
    r = client.put("/vehicles/1", headers=staff, json={"vehicle_status": "unavailable"})
    assert r.status_code == 200 and r.json()["vehicle_status"] == "unavailable" and r.json()["in_queue"] is False
    assert queue_plates(client) == ["GT-5678-24"]
    assert client.get("/queue").json()["queue"][0]["position"] == 1


def test_update_with_nothing_or_unknown_vehicle(client, staff):
    assert client.put("/vehicles/1", headers=staff, json={}).status_code == 422
    assert client.put("/vehicles/999", headers=staff, json={"available_seats": 1}).status_code == 404


def test_cannot_change_route_while_queued(client, staff):
    assert client.put("/vehicles/1", headers=staff, json={"route_id": 2}).status_code == 409
    assert client.put("/vehicles/3", headers=staff, json={"route_id": 2}).status_code == 200


def test_staff_can_assign_and_remove_a_driver(client, staff):
    assert client.put("/vehicles/3", headers=staff, json={"driver_id": 1}).json()["driver_name"] == "Kwame Asare"
    assert client.put("/vehicles/3", headers=staff, json={"driver_id": None}).json()["driver_id"] is None
    assert client.put("/vehicles/3", headers=staff, json={"driver_id": 999}).status_code == 422


def test_drivers_cannot_be_added_directly_and_manager_adds_route(client, manager):
    # New drivers only come from approved registration requests (see test_driver_requests.py).
    assert client.post("/drivers", headers=manager, json={"driver_name": "Esi Owusu"}).status_code == 405
    r = client.post("/routes", headers=manager, json={"destination": "Tema"})
    assert r.status_code == 201 and r.json()["destination"] == "Tema"
    assert client.post("/routes", headers=manager, json={"destination": "Tema"}).status_code == 409
    assert any(x["destination"] == "Tema" for x in client.get("/routes").json())


# ============================================================ trips
def test_trip_passenger_count_comes_from_seats_at_departure(client, staff):
    client.put("/vehicles/1", headers=staff, json={"available_seats": 4})  # 14 seats, 4 free -> 10 passengers
    client.post("/queue/departures", headers=staff, json={"vehicle_id": 1})
    trip = client.get("/trips", headers=staff).json()["trips"][0]
    assert trip["passengers"] == 10 and trip["driver_name"] == "Kwame Asare"
    assert trip["destination_name"] == "Madina" and trip["route_name"] == "Central - Madina"


def test_trip_passengers_unknown_when_no_seat_record(client, staff):
    trips = client.get("/trips", headers=staff).json()["trips"]  # sample departure predates any seat record
    assert trips[0]["registration_number"] == "GT-9012-24" and trips[0]["passengers"] is None


def test_trips_search_and_period_filter(client, staff):
    client.post("/queue/departures", headers=staff, json={"vehicle_id": 1})
    assert len(client.get("/trips", headers=staff).json()["trips"]) == 2
    only = client.get("/trips", headers=staff, params={"destination": "madina"}).json()["trips"]
    assert [t["registration_number"] for t in only] == ["GT-1234-24"]
    assert client.get("/trips", headers=staff, params={"destination": "zzz"}).json()["trips"] == []
    assert client.get("/trips", headers=staff, params={"destination": "%"}).json()["trips"] == []
    today = client.get("/trips", headers=staff, params={"period": "today"}).json()["trips"]
    assert "GT-1234-24" in [t["registration_number"] for t in today]
    assert client.get("/trips", headers=staff, params={"period": "century"}).status_code == 422


def test_trips_newest_first(client, staff):
    client.post("/queue/departures", headers=staff, json={"vehicle_id": 1})
    trips = client.get("/trips", headers=staff).json()["trips"]
    assert trips[0]["registration_number"] == "GT-1234-24"


# ============================================================ FR11, FR12 last updated
def test_last_updated_moves_forward_after_a_staff_change(client, staff):
    before = client.get("/queue").json()["last_updated"]
    client.put("/vehicles/1", headers=staff, json={"available_seats": 5})
    after = client.get("/queue").json()["last_updated"]
    assert before and after and after > before


def test_last_updated_ignores_sign_ins(client):
    before = client.get("/queue").json()["last_updated"]
    client.post("/auth/login", json={"email": "ama@station.com", "password": "staff123"})
    assert client.get("/queue").json()["last_updated"] == before


def test_last_updated_is_none_when_nothing_has_ever_been_recorded(client, db):
    for table in ("seat_availability", "vehicle_queue", "departures", "audit_log"):
        db.execute(f"DELETE FROM {table}" if table != "vehicle_queue" else "DELETE FROM vehicle_queue")
    assert client.get("/queue").json() == {"queue": [], "last_updated": None}


# ============================================================ offline sync (FR16-FR18)
def batch(records):
    return {"device_id": "phone-1", "records": records}


def rec(kind, vehicle_id, minutes_ago=1, **extra):
    return {"client_uuid": str(uuid.uuid4()), "type": kind, "station_id": 1, "vehicle_id": vehicle_id,
            "recorded_at": iso(minutes_ago), "payload": {}, **extra}


def test_sync_requires_sign_in(client):
    assert client.post("/sync/batch", json=batch([])).status_code == 401


def test_sync_applies_arrival_and_departure_in_recorded_order(client, staff):
    dep, arr = rec("vehicle_departure", 3, minutes_ago=2), rec("vehicle_arrival", 3, minutes_ago=9)
    r = client.post("/sync/batch", headers=staff, json=batch([dep, arr])).json()  # sent in the wrong order
    assert sorted(r["synced"]) == sorted([arr["client_uuid"], dep["client_uuid"]]) and r["failed"] == []
    assert queue_plates(client) == ["GT-1234-24", "GT-5678-24"]  # arrived then left again
    assert client.get("/trips", headers=staff).json()["trips"][0]["registration_number"] == "GT-9012-24"


def test_sync_keeps_the_time_the_action_happened(client, staff, db):
    a = rec("vehicle_arrival", 3, minutes_ago=30)
    client.post("/sync/batch", headers=staff, json=batch([a]))
    row = db.execute("SELECT arrival_time FROM vehicle_queue WHERE vehicle_id = 3").fetchone()
    assert abs((datetime.now(timezone.utc) - row["arrival_time"]).total_seconds() - 1800) < 60


def test_sync_is_safe_to_repeat(client, staff):
    a = rec("vehicle_arrival", 3)
    first = client.post("/sync/batch", headers=staff, json=batch([a])).json()
    again = client.post("/sync/batch", headers=staff, json=batch([a])).json()
    assert first["synced"] == again["synced"] == [a["client_uuid"]]
    assert queue_plates(client).count("GT-9012-24") == 1


def test_sync_reports_each_failure_without_blocking_the_rest(client, staff):
    good = rec("vehicle_arrival", 3, minutes_ago=3)
    dup = rec("vehicle_arrival", 1, minutes_ago=2)             # already in the queue
    missing = rec("vehicle_arrival", 999, minutes_ago=2)       # unknown vehicle
    future = rec("vehicle_arrival", 3, minutes_ago=-60)        # recorded in the future
    junk = {"client_uuid": str(uuid.uuid4()), "type": "teleport", "recorded_at": iso()}
    r = client.post("/sync/batch", headers=staff, json=batch([good, dup, missing, future, junk])).json()
    assert r["synced"] == [good["client_uuid"]]
    reasons = {f["client_uuid"]: f["error"] for f in r["failed"]}
    assert "already in the queue" in reasons[dup["client_uuid"]]
    assert "not found" in reasons[missing["client_uuid"]].lower()
    assert "future" in reasons[future["client_uuid"]]
    assert junk["client_uuid"] in reasons
    assert all(f["reason"] == f["error"] for f in r["failed"])  # both keys are provided


def test_failed_sync_record_can_succeed_when_sent_again(client, staff):
    a = rec("vehicle_arrival", 1)
    assert client.post("/sync/batch", headers=staff, json=batch([a])).json()["failed"]
    client.post("/queue/departures", headers=staff, json={"vehicle_id": 1})  # now it can arrive again
    assert client.post("/sync/batch", headers=staff, json=batch([a])).json()["synced"] == [a["client_uuid"]]


def test_sync_queue_update(client, staff):
    r = rec("queue_update", None, payload={"vehicle_ids": [2, 1]})
    assert client.post("/sync/batch", headers=staff, json=batch([r])).json()["synced"] == [r["client_uuid"]]
    assert queue_plates(client) == ["GT-5678-24", "GT-1234-24"]
    bad = rec("queue_update", None, payload={"vehicle_ids": "nope"})
    assert client.post("/sync/batch", headers=staff, json=batch([bad])).json()["failed"]


def test_sync_uses_the_signed_in_staff_not_the_one_claimed_in_the_data(client, staff, db):
    a = rec("vehicle_arrival", 3, staff_id=1)  # claims to be the manager
    client.post("/sync/batch", headers=staff, json=batch([a]))
    assert db.execute("SELECT recorded_by FROM vehicle_queue WHERE vehicle_id = 3").fetchone()["recorded_by"] == 2


def test_sync_results_are_stored(client, staff, db):
    ok, bad = rec("vehicle_arrival", 3), rec("vehicle_arrival", 1)
    client.post("/sync/batch", headers=staff, json=batch([ok, bad]))
    rows = {str(r["record_id"]): r for r in db.execute("SELECT * FROM offline_records WHERE record_id IS NOT NULL").fetchall()}
    assert rows[ok["client_uuid"]]["sync_status"] == "S" and rows[ok["client_uuid"]]["synced_at"] is not None
    assert rows[bad["client_uuid"]]["sync_status"] == "F" and rows[bad["client_uuid"]]["error_message"]


def test_sync_upload_alias_and_empty_batch(client, staff):
    assert client.post("/sync/upload", headers=staff, json=batch([])).json()["synced"] == []


def test_sync_download_is_public_and_complete(client):
    r = client.get("/sync/download")
    assert r.status_code == 200
    body = r.json()
    assert body["server_time"] and len(body["routes"]) == 3 and len(body["queue"]) == 2
    assert len(body["departures"]) == 1 and body["stations"]
    assert "phone" not in str(body).lower() and "password" not in str(body).lower()


# ============================================================ activity log and housekeeping
def test_activity_log_records_who_did_what(client, manager, staff):
    client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 3})
    log = client.get("/activity", headers=manager).json()
    top = log[0]
    assert top["action"] == "VEHICLE_ARRIVAL" and top["staff_name"] == "Ama Mensah"
    assert any(e["action"] == "LOGIN" for e in log)


def test_failed_logins_are_logged(client, manager):
    client.post("/auth/login", json={"email": "ama@station.com", "password": "bad"})
    assert any(e["action"] == "LOGIN_FAILED" for e in client.get("/activity", headers=manager).json())


def test_failed_action_leaves_no_partial_changes(client, staff):
    assert client.put("/vehicles/1", headers=staff, json={"vehicle_status": "departed", "available_seats": 1}).status_code == 409
    v = next(v for v in client.get("/vehicles", headers=staff).json()["vehicles"] if v["vehicle_id"] == 1)
    assert v["available_seats"] == 8  # the seat change was undone too


def test_health_and_docs(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}
    assert client.get("/docs").status_code == 200


def test_cors_allows_the_dashboard_origin(client):
    r = client.options("/queue", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    r = client.options("/queue", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


# ============================================================ two people at the same time
def test_simultaneous_arrivals_get_unique_positions(client, manager, staff):
    from concurrent.futures import ThreadPoolExecutor
    ids = [3]
    for plate in ("CC-1-24", "CC-2-24", "CC-3-24"):
        ids.append(client.post("/vehicles", headers=manager,
                               json={"registration_number": plate, "route_id": 1, "capacity": 14}).json()["vehicle_id"])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda vid: client.post("/queue/arrivals", headers=staff, json={"vehicle_id": vid}), ids))
    assert all(r.status_code == 201 for r in results)
    assert sorted(q["position"] for q in client.get("/queue").json()["queue"]) == [1, 2, 3, 4, 5, 6]


def test_same_vehicle_recorded_twice_at_once_is_only_queued_once(client, staff):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: client.post("/queue/arrivals", headers=staff, json={"vehicle_id": 3}), range(5)))
    assert sorted(r.status_code for r in results) == [201, 409, 409, 409, 409]
    assert queue_plates(client).count("GT-9012-24") == 1
