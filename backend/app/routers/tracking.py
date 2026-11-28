"""Live tracking: where each vehicle is, how far it is from its destination, and whether it is
getting closer. Reading is public (the passenger app can use it). Sending a position needs a staff sign-in.

How the numbers are worked out
  * distance  : straight-line distance (great-circle) from the vehicle to its route's destination.
                Real road distance is longer, so treat it as "at least this far".
  * direction : the vehicle's latest position is compared with an earlier one at least 50 m away
                (within the last 15 minutes).  closer -> 'approaching', farther -> 'moving_away',
                no real movement -> 'stopped'.  Within 200 m of the destination -> 'arrived'.
  * ETA       : distance / speed, only while approaching and moving at 5 km/h or more.
                The speed is the one reported, or worked out from the last two positions.
  * a position older than 5 minutes is flagged 'stale' and no direction or ETA is claimed.
"""
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, Depends

from ..db import get_conn
from ..errors import ApiError
from ..schemas import LocationIn, PositionIn
from ..security import current_staff, require_manager
from ..services import audit

router = APIRouter(prefix="/tracking", tags=["Tracking"])

SHOW_FOR_HOURS = 6          # vehicles with no report for this long disappear from the map
STALE_AFTER_MINUTES = 5     # older than this: show 'No recent signal'
LOOKBACK_MINUTES = 15       # how far back to look for an earlier position
MIN_MOVE_KM = 0.05          # less movement than this counts as 'stopped'
ARRIVED_KM = 0.2            # closer than this to the destination counts as 'arrived'
MIN_SPEED_KMH = 5           # below this no ETA is given


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Straight-line distance in kilometres between two latitude/longitude points."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(a))


def _f(value):
    return None if value is None else float(value)


def describe(history: list[dict], dest_lat, dest_lon, now: datetime) -> dict:
    """history: this vehicle's positions, newest first. Returns distance, direction and ETA."""
    latest = history[0]
    age_min = (now - latest["recorded_at"]).total_seconds() / 60
    stale = age_min > STALE_AFTER_MINUTES
    out = {"stale": stale, "age_minutes": round(age_min, 1), "distance_km": None,
           "direction": "unknown", "eta_minutes": None, "speed_kmh": _f(latest["speed_kmh"])}
    if dest_lat is None or dest_lon is None:
        out["direction"] = "no_destination"
        return out
    lat, lon = float(latest["latitude"]), float(latest["longitude"])
    dist = haversine_km(lat, lon, dest_lat, dest_lon)
    out["distance_km"] = round(dist, 2)
    if stale:
        return out
    if dist <= ARRIVED_KM:
        out["direction"] = "arrived"
        out["eta_minutes"] = 0
        return out

    # earlier position, at least MIN_MOVE_KM away from the latest, within the look-back window
    earlier = None
    for h in history[1:]:
        if (latest["recorded_at"] - h["recorded_at"]) > timedelta(minutes=LOOKBACK_MINUTES):
            break
        if haversine_km(lat, lon, float(h["latitude"]), float(h["longitude"])) >= MIN_MOVE_KM:
            earlier = h
            break
    if earlier is None:
        out["direction"] = "stopped"
        return out

    before = haversine_km(float(earlier["latitude"]), float(earlier["longitude"]), dest_lat, dest_lon)
    out["direction"] = "approaching" if dist < before else "moving_away"
    if out["direction"] == "approaching":
        speed = out["speed_kmh"]
        if speed is None:
            hours = (latest["recorded_at"] - earlier["recorded_at"]).total_seconds() / 3600
            moved = haversine_km(lat, lon, float(earlier["latitude"]), float(earlier["longitude"]))
            speed = moved / hours if hours > 0 else None
        if speed is not None and speed >= MIN_SPEED_KMH:
            out["eta_minutes"] = max(1, round(dist / speed * 60))
            out["speed_kmh"] = round(speed, 1)
    return out


@router.get("/vehicles")
def tracked_vehicles(conn=Depends(get_conn, scope="function")):
    """Every vehicle that reported a position recently, with distance, direction and ETA."""
    now = conn.execute("SELECT CURRENT_TIMESTAMP AS t").fetchone()["t"]
    vehicles = conn.execute(
        """SELECT v.vehicle_id, v.registration_number, v.vehicle_status, r.route_name,
                  de.destination_id, de.destination_name AS destination,
                  de.latitude AS dest_lat, de.longitude AS dest_lon
           FROM vehicles v
           JOIN routes r ON r.route_id = v.route_id
           JOIN destinations de ON de.destination_id = r.destination_id
           WHERE EXISTS (SELECT 1 FROM vehicle_positions p
                         WHERE p.vehicle_id = v.vehicle_id
                           AND p.recorded_at >= CURRENT_TIMESTAMP - make_interval(hours => %s))
           ORDER BY v.registration_number""",
        (SHOW_FOR_HOURS,),
    ).fetchall()

    result = []
    for v in vehicles:
        history = conn.execute(
            "SELECT latitude, longitude, speed_kmh, recorded_at FROM vehicle_positions "
            "WHERE vehicle_id = %s ORDER BY recorded_at DESC, position_id DESC LIMIT 30",
            (v["vehicle_id"],),
        ).fetchall()
        info = describe(history, _f(v["dest_lat"]), _f(v["dest_lon"]), now)
        result.append({
            "vehicle_id": v["vehicle_id"],
            "registration_number": v["registration_number"],
            "vehicle_status": v["vehicle_status"],
            "route_name": v["route_name"],
            "destination": v["destination"],
            "destination_latitude": _f(v["dest_lat"]),
            "destination_longitude": _f(v["dest_lon"]),
            "latitude": float(history[0]["latitude"]),
            "longitude": float(history[0]["longitude"]),
            "recorded_at": history[0]["recorded_at"],
            **info,
        })
    station = conn.execute(
        "SELECT station_id, station_name, latitude, longitude FROM stations WHERE is_active ORDER BY station_id LIMIT 1"
    ).fetchone()
    if station:
        station = {**station, "latitude": _f(station["latitude"]), "longitude": _f(station["longitude"])}
    return {"vehicles": result, "station": station, "server_time": now}


@router.get("/destinations")
def destinations(conn=Depends(get_conn, scope="function")):
    """Destinations and where they are on the map (latitude/longitude are null until someone sets them)."""
    rows = conn.execute(
        "SELECT destination_id, destination_name, latitude, longitude FROM destinations ORDER BY destination_name"
    ).fetchall()
    return [{**r, "latitude": _f(r["latitude"]), "longitude": _f(r["longitude"])} for r in rows]


@router.post("/position", status_code=201)
def report_position(body: PositionIn, staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    """Record where a vehicle is now. `recorded_at` is optional (use it to send a delayed report)."""
    vehicle = conn.execute(
        "SELECT v.vehicle_id, d.account_id FROM vehicles v LEFT JOIN drivers d ON d.driver_id = v.driver_id "
        "WHERE v.vehicle_id = %s", (body.vehicle_id,)
    ).fetchone()
    if not vehicle:
        raise ApiError(404, "Vehicle not found")
    if staff["role"] == "driver" and vehicle["account_id"] != staff["staff_id"]:
        raise ApiError(403, "You can only share the location of your own vehicle")
    when = body.recorded_at
    if when is not None:
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when > datetime.now(timezone.utc) + timedelta(minutes=2):
            raise ApiError(422, "recorded_at cannot be in the future")
    # Not written to the audit log: positions arrive every few seconds and would flood it.
    row = conn.execute(
        "INSERT INTO vehicle_positions (vehicle_id, latitude, longitude, speed_kmh, recorded_at, recorded_by) "
        "VALUES (%s, %s, %s, %s, COALESCE(%s::timestamptz, CURRENT_TIMESTAMP), %s) "
        "RETURNING position_id, recorded_at",
        (body.vehicle_id, body.latitude, body.longitude, body.speed_kmh, when, staff["staff_id"]),
    ).fetchone()
    return {"ok": True, **row}


@router.put("/destinations/{destination_id}/location")
def set_destination_location(destination_id: int, body: LocationIn, staff=Depends(require_manager),
                             conn=Depends(get_conn, scope="function")):
    row = conn.execute(
        "UPDATE destinations SET latitude = %s, longitude = %s WHERE destination_id = %s "
        "RETURNING destination_id, destination_name, latitude, longitude",
        (body.latitude, body.longitude, destination_id),
    ).fetchone()
    if not row:
        raise ApiError(404, "Destination not found")
    audit(conn, staff["staff_id"], "DESTINATION_LOCATION_SET", "destinations", destination_id,
          {"latitude": body.latitude, "longitude": body.longitude})
    return {**row, "latitude": _f(row["latitude"]), "longitude": _f(row["longitude"])}
