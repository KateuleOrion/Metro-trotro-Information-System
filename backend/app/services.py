"""Business rules shared by the API routes and by offline synchronisation.

Queue rules (see the vehicle_queue table):
  * A vehicle can have only one active queue entry (status 'waiting' or 'loading').
  * Active entries are numbered 1..n with no gaps. Removing or departing a vehicle renumbers the rest.
  * Every change is written to audit_log.
"""
from datetime import datetime, timezone
from typing import Optional

from psycopg import errors as pg
from psycopg.types.json import Jsonb

from . import config
from .errors import ApiError

ACTIVE_SQL = "('waiting', 'loading')"

LATEST_SEATS_JOIN = """
LEFT JOIN LATERAL (
    SELECT sa.available_seats, sa.last_updated
    FROM seat_availability sa
    WHERE sa.vehicle_id = v.vehicle_id
    ORDER BY sa.last_updated DESC, sa.seat_record_id DESC
    LIMIT 1
) seat ON TRUE
"""


# ---------------------------------------------------------------- helpers
def audit(conn, staff_id: Optional[int], action: str, entity: str, entity_id=None, details: Optional[dict] = None):
    conn.execute(
        "INSERT INTO audit_log (staff_id, action, entity_name, entity_id, details) VALUES (%s, %s, %s, %s, %s)",
        (staff_id, action, entity, None if entity_id is None else str(entity_id),
         None if details is None else Jsonb(details)),
    )


def data_last_updated(conn):
    """Time of the most recent staff change, or None if nothing has been recorded.
    Login events are not counted: they do not change what passengers see."""
    row = conn.execute(
        """SELECT GREATEST(
               (SELECT MAX(last_updated) FROM seat_availability),
               (SELECT MAX(last_updated) FROM vehicle_queue),
               (SELECT MAX(departure_time) FROM departures),
               (SELECT MAX(created_at) FROM audit_log WHERE action NOT IN ('LOGIN', 'LOGIN_FAILED'))
           ) AS t"""
    ).fetchone()
    return row["t"]


def lock_station(conn, station_id: int):
    """Stops two people changing the same station's queue at the same moment."""
    conn.execute("SELECT pg_advisory_xact_lock(7001, %s)", (station_id,))


def get_vehicle(conn, vehicle_id: int, lock: bool = False) -> dict:
    row = conn.execute(
        "SELECT v.*, r.station_id FROM vehicles v JOIN routes r ON r.route_id = v.route_id "
        "WHERE v.vehicle_id = %s" + (" FOR UPDATE OF v" if lock else ""),
        (vehicle_id,),
    ).fetchone()
    if not row:
        raise ApiError(404, "Vehicle not found")
    return row


def active_entry(conn, vehicle_id: int, lock: bool = False):
    return conn.execute(
        f"SELECT * FROM vehicle_queue WHERE vehicle_id = %s AND queue_status IN {ACTIVE_SQL}"
        + (" FOR UPDATE" if lock else ""),
        (vehicle_id,),
    ).fetchone()


def active_queue_rows(conn, station_id: int) -> list[dict]:
    return conn.execute(
        f"SELECT queue_id, vehicle_id FROM vehicle_queue WHERE station_id = %s AND queue_status IN {ACTIVE_SQL} "
        "ORDER BY queue_position",
        (station_id,),
    ).fetchall()


def renumber(conn, queue_ids: list[int]):
    """Give the listed queue entries positions 1..n in the order given.
    Done in two steps because positions must stay unique at every moment."""
    if len(queue_ids) > config.MAX_QUEUE:
        raise ApiError(409, "The queue is too long")
    if not queue_ids:
        return
    conn.execute("UPDATE vehicle_queue SET queue_position = queue_position + 500 WHERE queue_id = ANY(%s)", (queue_ids,))
    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE vehicle_queue SET queue_position = %s, last_updated = CURRENT_TIMESTAMP WHERE queue_id = %s",
            [(i + 1, qid) for i, qid in enumerate(queue_ids)],
        )


# ---------------------------------------------------------------- routes and drivers typed by staff
def find_or_create_route(conn, staff_id: int, destination: str, station_id: Optional[int] = None) -> int:
    """Returns the id of the active route to this destination at the station, creating it if needed.
    The route is named 'Station - Destination', the same way POST /routes names it."""
    station_id = station_id or config.DEFAULT_STATION_ID
    station = conn.execute(
        "SELECT station_name FROM stations WHERE station_id = %s AND is_active", (station_id,)
    ).fetchone()
    if not station:
        raise ApiError(404, "Station not found")
    existing = conn.execute(
        "SELECT r.route_id FROM routes r JOIN destinations d ON d.destination_id = r.destination_id "
        "WHERE r.station_id = %s AND r.is_active AND lower(d.destination_name) = lower(%s) "
        "ORDER BY r.route_id LIMIT 1",
        (station_id, destination),
    ).fetchone()
    if existing:
        return existing["route_id"]
    dest = conn.execute(
        "SELECT destination_id FROM destinations WHERE lower(destination_name) = lower(%s)", (destination,)
    ).fetchone()
    if not dest:
        dest = conn.execute(
            "INSERT INTO destinations (destination_name) VALUES (%s) RETURNING destination_id", (destination,)
        ).fetchone()
    origin = station["station_name"]
    route_name = f"{origin} - {destination}"
    try:
        row = conn.execute(
            "INSERT INTO routes (route_name, origin, destination_id, station_id) VALUES (%s, %s, %s, %s) "
            "RETURNING route_id",
            (route_name, origin, dest["destination_id"], station_id),
        ).fetchone()
    except pg.UniqueViolation:
        # same route name already used for an inactive route or a different spelling
        raise ApiError(409, "A route with this name already exists at this station")
    audit(conn, staff_id, "ROUTE_CREATED", "routes", row["route_id"], {"route_name": route_name})
    return row["route_id"]


def normalize_phone(phone: str) -> str:
    """One way of writing each phone number, so '+233 24 123 4567', '233241234567' and
    '024-123-4567' all match the same account."""
    text = phone.strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits.startswith("233") and len(digits) == 12:  # Ghana country code -> local 0XXXXXXXXX
        return "0" + digits[3:]
    return ("+" + digits) if text.startswith("+") else digits


# ---------------------------------------------------------------- queue actions
def record_arrival(conn, staff_id: int, vehicle_id: int, when: Optional[datetime] = None) -> dict:
    v = get_vehicle(conn, vehicle_id, lock=True)
    if v["vehicle_status"] == "unavailable":
        raise ApiError(409, "This vehicle is marked unavailable. Set it to available first")
    station_id = v["station_id"]
    lock_station(conn, station_id)
    if active_entry(conn, vehicle_id):
        raise ApiError(409, "Vehicle is already in the queue")
    n = conn.execute(
        f"SELECT COUNT(*) AS n, COALESCE(MAX(queue_position), 0) AS top FROM vehicle_queue "
        f"WHERE station_id = %s AND queue_status IN {ACTIVE_SQL}",
        (station_id,),
    ).fetchone()
    if n["n"] >= config.MAX_QUEUE:
        raise ApiError(409, "The queue is full")
    row = conn.execute(
        "INSERT INTO vehicle_queue (vehicle_id, station_id, queue_position, arrival_time, queue_status, recorded_by) "
        "VALUES (%s, %s, %s, COALESCE(%s::timestamptz, CURRENT_TIMESTAMP), 'waiting', %s) "
        "RETURNING queue_id, queue_position, arrival_time",
        (vehicle_id, station_id, n["top"] + 1, when, staff_id),
    ).fetchone()
    conn.execute("UPDATE vehicles SET vehicle_status = 'queued' WHERE vehicle_id = %s", (vehicle_id,))
    audit(conn, staff_id, "VEHICLE_ARRIVAL", "vehicle_queue", row["queue_id"],
          {"vehicle_id": vehicle_id, "position": row["queue_position"]})
    return row


def record_departure(conn, staff_id: int, vehicle_id: int, when: Optional[datetime] = None) -> dict:
    v = get_vehicle(conn, vehicle_id, lock=True)
    station_id = v["station_id"]
    lock_station(conn, station_id)
    entry = active_entry(conn, vehicle_id, lock=True)
    if not entry:
        raise ApiError(409, "Vehicle is not in the queue")
    conn.execute(
        "UPDATE vehicle_queue SET queue_status = 'departed', departed_at = COALESCE(%s::timestamptz, CURRENT_TIMESTAMP), "
        "last_updated = CURRENT_TIMESTAMP WHERE queue_id = %s",
        (when, entry["queue_id"]),
    )
    dep = conn.execute(
        "INSERT INTO departures (vehicle_id, route_id, station_id, departure_time, recorded_by) "
        "VALUES (%s, %s, %s, COALESCE(%s::timestamptz, CURRENT_TIMESTAMP), %s) "
        "RETURNING departure_id, departure_time",
        (vehicle_id, v["route_id"], station_id, when, staff_id),
    ).fetchone()
    conn.execute("UPDATE vehicles SET vehicle_status = 'departed' WHERE vehicle_id = %s", (vehicle_id,))
    renumber(conn, [r["queue_id"] for r in active_queue_rows(conn, station_id)])
    audit(conn, staff_id, "VEHICLE_DEPARTURE", "departures", dep["departure_id"], {"vehicle_id": vehicle_id})
    return dep


def remove_from_queue(conn, staff_id: int, vehicle_id: int, new_status: str = "available") -> None:
    """Takes a vehicle out of the queue without a departure (for example it broke down)."""
    v = get_vehicle(conn, vehicle_id, lock=True)
    lock_station(conn, v["station_id"])
    entry = active_entry(conn, vehicle_id, lock=True)
    if not entry:
        raise ApiError(409, "Vehicle is not in the queue")
    conn.execute(
        "UPDATE vehicle_queue SET queue_status = 'cancelled', last_updated = CURRENT_TIMESTAMP WHERE queue_id = %s",
        (entry["queue_id"],),
    )
    conn.execute("UPDATE vehicles SET vehicle_status = %s WHERE vehicle_id = %s", (new_status, vehicle_id))
    renumber(conn, [r["queue_id"] for r in active_queue_rows(conn, v["station_id"])])
    audit(conn, staff_id, "QUEUE_REMOVED", "vehicle_queue", entry["queue_id"], {"vehicle_id": vehicle_id})


def reorder_queue(conn, staff_id: int, station_id: int, vehicle_ids: list[int]) -> None:
    lock_station(conn, station_id)
    current = active_queue_rows(conn, station_id)
    if len(set(vehicle_ids)) != len(vehicle_ids) or sorted(vehicle_ids) != sorted(r["vehicle_id"] for r in current):
        raise ApiError(409, "The queue has changed. Refresh the page and try again")
    by_vehicle = {r["vehicle_id"]: r["queue_id"] for r in current}
    renumber(conn, [by_vehicle[vid] for vid in vehicle_ids])
    audit(conn, staff_id, "QUEUE_REORDERED", "vehicle_queue", station_id, {"vehicle_ids": vehicle_ids})


# ---------------------------------------------------------------- vehicles
VEHICLE_ROWS_SQL = f"""
SELECT v.vehicle_id, v.registration_number, v.route_id, r.route_name, r.origin,
       de.destination_name AS destination, v.capacity, v.vehicle_status, v.driver_id,
       dr.driver_name, seat.available_seats,
       EXISTS (SELECT 1 FROM vehicle_queue q
               WHERE q.vehicle_id = v.vehicle_id AND q.queue_status IN {ACTIVE_SQL}) AS in_queue
FROM vehicles v
JOIN routes r ON r.route_id = v.route_id
JOIN destinations de ON de.destination_id = r.destination_id
LEFT JOIN drivers dr ON dr.driver_id = v.driver_id
{LATEST_SEATS_JOIN}
"""


def vehicle_rows(conn, vehicle_id: Optional[int] = None) -> list[dict]:
    if vehicle_id is None:
        return conn.execute(VEHICLE_ROWS_SQL + " ORDER BY v.vehicle_id").fetchall()
    return conn.execute(VEHICLE_ROWS_SQL + " WHERE v.vehicle_id = %s", (vehicle_id,)).fetchall()


def set_seats(conn, staff_id: int, vehicle_id: int, capacity: int, seats: int) -> None:
    if seats > capacity:
        raise ApiError(422, f"Seats available cannot exceed the vehicle's capacity ({capacity})")
    conn.execute(
        "INSERT INTO seat_availability (vehicle_id, available_seats, recorded_by) VALUES (%s, %s, %s)",
        (vehicle_id, seats, staff_id),
    )


def update_vehicle(conn, staff_id: int, vehicle_id: int, changes: dict) -> None:
    v = get_vehicle(conn, vehicle_id, lock=True)
    entry = active_entry(conn, vehicle_id, lock=True)
    sets, params = [], []

    if "route_id" in changes and changes["route_id"] is not None and changes["route_id"] != v["route_id"]:
        if entry:
            raise ApiError(409, "Remove the vehicle from the queue before changing its route")
        sets.append("route_id = %s")
        params.append(changes["route_id"])
    if "driver_id" in changes and changes["driver_id"] != v["driver_id"]:
        sets.append("driver_id = %s")
        params.append(changes["driver_id"])

    status = changes.get("vehicle_status")
    if status and status != v["vehicle_status"]:
        if status == "departed":
            raise ApiError(409, "Use 'Record departure' in the queue to mark a vehicle as departed")
        if status in ("queued", "loading"):
            if not entry:
                raise ApiError(409, "The vehicle is not in the queue. Record its arrival first")
            conn.execute(
                "UPDATE vehicle_queue SET queue_status = %s, last_updated = CURRENT_TIMESTAMP WHERE queue_id = %s",
                ("loading" if status == "loading" else "waiting", entry["queue_id"]),
            )
        elif status == "available":
            if entry:
                raise ApiError(409, "The vehicle is in the queue. Remove it from the queue first")
        elif status == "unavailable" and entry:
            remove_from_queue(conn, staff_id, vehicle_id, new_status="unavailable")
        if status != "unavailable" or not entry:
            sets.append("vehicle_status = %s")
            params.append(status)

    if sets:
        conn.execute(f"UPDATE vehicles SET {', '.join(sets)} WHERE vehicle_id = %s", (*params, vehicle_id))
    if changes.get("available_seats") is not None:
        set_seats(conn, staff_id, vehicle_id, v["capacity"], changes["available_seats"])
    audit(conn, staff_id, "VEHICLE_UPDATED", "vehicles", vehicle_id, {k: v_ for k, v_ in changes.items()})


# ---------------------------------------------------------------- estimates
def estimate_wait_minutes(conn, route_id: int):
    """Estimated minutes until the next vehicle on this route leaves.

    Uses the gaps between the route's last (up to) 5 departures in the past 24 hours.
    Needs at least 2 departures; otherwise returns (None, count) so the apps show 'Unavailable'.
    wait = average gap - minutes since the last departure (never below 0)."""
    rows = conn.execute(
        "SELECT departure_time FROM departures WHERE route_id = %s "
        "AND departure_time >= CURRENT_TIMESTAMP - INTERVAL '24 hours' ORDER BY departure_time DESC LIMIT 5",
        (route_id,),
    ).fetchall()
    if len(rows) < 2:
        return None, len(rows)
    times = [r["departure_time"] for r in rows]
    gaps = [(times[i] - times[i + 1]).total_seconds() for i in range(len(times) - 1)]
    avg_gap = sum(gaps) / len(gaps)
    since_last = (datetime.now(timezone.utc) - times[0]).total_seconds()
    return max(0, round((avg_gap - since_last) / 60)), len(rows)
