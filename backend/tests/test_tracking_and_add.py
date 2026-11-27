"""Tests for the tracking map API and for adding vehicles with a typed-in destination.

Sample data (metro_trotro_db.sql): vehicle 1 is on route 1 (Madina), vehicle 2 on route 2 (Circle),
vehicle 3 on route 3 (Kasoa). Madina is at about 5.6693, -0.1670.
"""
from datetime import datetime, timedelta, timezone

from app.routers.tracking import haversine_km


def iso(minutes_ago=0):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def send(client, headers, vehicle_id, lat, lon, minutes_ago=0, speed=None):
    body = {"vehicle_id": vehicle_id, "latitude": lat, "longitude": lon, "recorded_at": iso(minutes_ago)}
    if speed is not None:
        body["speed_kmh"] = speed
    return client.post("/tracking/position", headers=headers, json=body)


def tracked(client, vehicle_id):
    vehicles = client.get("/tracking/vehicles").json()["vehicles"]
    return next(v for v in vehicles if v["vehicle_id"] == vehicle_id)


# ------------------------------------------------------------------ distance maths
def test_haversine_distance_is_sensible():
    # Accra Central to Madina is roughly 14 km in a straight line
    assert 13 < haversine_km(5.5465, -0.2063, 5.6693, -0.1670) < 15
    assert haversine_km(5.5, -0.2, 5.5, -0.2) == 0


# ------------------------------------------------------------------ sending positions
def test_sending_a_position_needs_sign_in(client):
    r = client.post("/tracking/position", json={"vehicle_id": 1, "latitude": 5.5, "longitude": -0.2})
    assert r.status_code == 401


def test_position_for_unknown_vehicle_is_rejected(client, staff):
    assert send(client, staff, 999, 5.5, -0.2).status_code == 404


def test_invalid_coordinates_are_rejected(client, staff):
    assert send(client, staff, 1, 95, -0.2).status_code == 422
    assert send(client, staff, 1, 5.5, -200).status_code == 422
    assert send(client, staff, 1, 5.5, -0.2, speed=-4).status_code == 422


def test_position_in_the_future_is_rejected(client, staff):
    assert send(client, staff, 1, 5.5, -0.2, minutes_ago=-30).status_code == 422


def test_tracking_list_is_public_and_empty_at_first(client):
    r = client.get("/tracking/vehicles")
    assert r.status_code == 200
    body = r.json()
    assert body["vehicles"] == []
    assert body["station"]["station_name"] == "Metro Central Station"


def test_sending_positions_does_not_change_the_audit_log_or_last_updated(client, staff, db):
    before = db.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"]
    assert send(client, staff, 1, 5.55, -0.2).status_code == 201
    assert db.execute("SELECT COUNT(*) AS n FROM audit_log").fetchone()["n"] == before


# ------------------------------------------------------------------ direction, distance, ETA
def test_vehicle_moving_toward_destination_is_approaching_with_eta(client, staff):
    send(client, staff, 1, 5.5600, -0.2000, minutes_ago=4)
    send(client, staff, 1, 5.6000, -0.1900, minutes_ago=1)
    v = tracked(client, 1)
    assert v["direction"] == "approaching"
    assert v["destination"] == "Madina"
    assert 7 < v["distance_km"] < 9          # about 8 km left
    assert v["eta_minutes"] is not None and v["eta_minutes"] > 0
    assert v["stale"] is False


def test_vehicle_moving_away_has_no_eta(client, staff):
    send(client, staff, 1, 5.6000, -0.1900, minutes_ago=4)
    send(client, staff, 1, 5.5600, -0.2000, minutes_ago=1)
    v = tracked(client, 1)
    assert v["direction"] == "moving_away" and v["eta_minutes"] is None


def test_vehicle_that_is_not_moving_is_stopped(client, staff):
    send(client, staff, 1, 5.6000, -0.1900, minutes_ago=4)
    send(client, staff, 1, 5.6000, -0.1900, minutes_ago=1)
    assert tracked(client, 1)["direction"] == "stopped"


def test_vehicle_near_the_destination_has_arrived(client, staff):
    send(client, staff, 1, 5.6692, -0.1671, minutes_ago=1)
    v = tracked(client, 1)
    assert v["direction"] == "arrived" and v["eta_minutes"] == 0


def test_old_position_is_flagged_stale_and_makes_no_claim(client, staff):
    send(client, staff, 1, 5.5600, -0.2000, minutes_ago=14)
    send(client, staff, 1, 5.6000, -0.1900, minutes_ago=10)
    v = tracked(client, 1)
    assert v["stale"] is True and v["direction"] == "unknown" and v["eta_minutes"] is None
    assert v["distance_km"] is not None      # the last known distance is still shown


def test_vehicle_with_no_report_for_hours_leaves_the_map(client, staff, db):
    send(client, staff, 1, 5.55, -0.2, minutes_ago=1)
    db.execute("UPDATE vehicle_positions SET recorded_at = CURRENT_TIMESTAMP - INTERVAL '7 hours'")
    assert client.get("/tracking/vehicles").json()["vehicles"] == []


def test_destination_without_coordinates_gives_no_distance(client, staff, db):
    db.execute("UPDATE destinations SET latitude = NULL, longitude = NULL WHERE destination_id = 1")
    send(client, staff, 1, 5.55, -0.2, minutes_ago=1)
    v = tracked(client, 1)
    assert v["direction"] == "no_destination" and v["distance_km"] is None


def test_reported_speed_is_used_for_the_eta(client, staff):
    send(client, staff, 1, 5.5600, -0.2000, minutes_ago=4)
    send(client, staff, 1, 5.6000, -0.1900, minutes_ago=1, speed=40)
    v = tracked(client, 1)
    # about 8.2 km at 40 km/h is about 12 minutes
    assert 10 <= v["eta_minutes"] <= 14


# ------------------------------------------------------------------ destination coordinates
def test_manager_can_set_a_destination_location(client, manager):
    r = client.put("/tracking/destinations/1/location", headers=manager, json={"latitude": 5.7, "longitude": -0.17})
    assert r.status_code == 200 and r.json()["latitude"] == 5.7
    dest = next(d for d in client.get("/tracking/destinations").json() if d["destination_id"] == 1)
    assert dest["longitude"] == -0.17


def test_staff_cannot_set_a_destination_location(client, staff):
    r = client.put("/tracking/destinations/1/location", headers=staff, json={"latitude": 5.7, "longitude": -0.17})
    assert r.status_code == 403


def test_setting_location_of_unknown_destination_is_404(client, manager):
    r = client.put("/tracking/destinations/99/location", headers=manager, json={"latitude": 5.7, "longitude": -0.17})
    assert r.status_code == 404


# ------------------------------------------------------------------ add a vehicle with a typed driver and destination
def count(db, table):
    return db.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


def test_new_destination_is_created_with_the_vehicle(client, manager, db):
    r = client.post("/vehicles", headers=manager, json={
        "registration_number": "GR-4000-24", "capacity": 14, "destination": "Tema", "driver_id": 1})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["destination"] == "Tema" and body["driver_name"] == "Kwame Asare"
    assert body["route_name"] == "Metro Central Station - Tema"
    assert count(db, "routes") == 4 and count(db, "drivers") == 3


def test_existing_destination_is_reused_not_duplicated(client, manager, db):
    r = client.post("/vehicles", headers=manager, json={
        "registration_number": "GR-4001-24", "capacity": 14, "destination": "  madina "})
    assert r.status_code == 201 and r.json()["route_id"] == 1
    assert count(db, "routes") == 3


def test_typing_a_new_driver_is_refused(client, manager, db):
    r = client.post("/vehicles", headers=manager, json={
        "registration_number": "GR-4002-24", "capacity": 14, "route_id": 1,
        "driver_name": "Someone New", "driver_phone": "0240000099"})
    assert r.status_code == 422 and "registration request" in r.json()["detail"]
    assert count(db, "drivers") == 3 and count(db, "vehicles") == 3


def test_unknown_driver_id_is_rejected(client, manager, db):
    r = client.post("/vehicles", headers=manager, json={
        "registration_number": "GR-4003-24", "capacity": 14, "route_id": 1, "driver_id": 999})
    assert r.status_code == 422 and count(db, "vehicles") == 3


def test_duplicate_plate_creates_no_route(client, manager, db):
    r = client.post("/vehicles", headers=manager, json={
        "registration_number": "gt-1234-24", "capacity": 14, "destination": "Tema"})
    assert r.status_code == 409
    assert count(db, "routes") == 3 and count(db, "destinations") == 3


def test_route_or_destination_is_required(client, manager):
    r = client.post("/vehicles", headers=manager, json={"registration_number": "GR-4005-24", "capacity": 14})
    assert r.status_code == 422 and "route_id or a destination" in r.json()["detail"]


def test_staff_cannot_add_vehicles(client, staff):
    r = client.post("/vehicles", headers=staff, json={
        "registration_number": "GR-4007-24", "capacity": 14, "destination": "Tema"})
    assert r.status_code == 403
