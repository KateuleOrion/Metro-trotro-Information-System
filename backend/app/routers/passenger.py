"""Public, read-only endpoints for the passenger app and the driver view. No sign-in needed."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from .. import config
from ..db import get_conn
from ..errors import ApiError
from ..services import ACTIVE_SQL, LATEST_SEATS_JOIN, data_last_updated, estimate_wait_minutes
from .trips import _like
from ..booking_service import create_booking, cancel_booking
from ..schemas import BookingCreate
from ..security import current_passenger

router = APIRouter(tags=["Passenger and driver"])

STATUS_LABELS = {"waiting": "Waiting in queue", "loading": "Loading"}


@router.get("/passenger/search")
def search(
    from_: str = Query("", alias="from", max_length=100),
    to: str = Query("", max_length=100),
    conn=Depends(get_conn),
):
    """Routes matching what the passenger typed, with the vehicles queued for each.
    Leave both fields empty to list every route. Missing values are returned as null so
    the app can show 'Unavailable' (fares are not stored in the database yet)."""
    origin_text, dest_text = from_.strip(), to.strip()
    routes = conn.execute(
        """SELECT r.route_id, r.route_name, r.origin, de.destination_name AS destination
           FROM routes r JOIN destinations de ON de.destination_id = r.destination_id
           WHERE r.is_active
             AND (%(o)s = '' OR r.origin ILIKE %(olike)s)
             AND (%(d)s = '' OR de.destination_name ILIKE %(dlike)s OR r.route_name ILIKE %(dlike)s)
           ORDER BY r.route_name""",
        {"o": origin_text, "olike": _like(origin_text), "d": dest_text, "dlike": _like(dest_text)},
    ).fetchall()

    results = []
    for route in routes:
        vehicles = conn.execute(
            f"""SELECT v.vehicle_id, v.registration_number, q.queue_position, q.queue_status, q.arrival_time,
                       seat.available_seats
                FROM vehicle_queue q
                JOIN vehicles v ON v.vehicle_id = q.vehicle_id
                {LATEST_SEATS_JOIN}
                WHERE v.route_id = %s AND q.queue_status IN {ACTIVE_SQL}
                ORDER BY q.queue_position""",
            (route["route_id"],),
        ).fetchall()
        for v in vehicles:
            v["status_label"] = STATUS_LABELS[v["queue_status"]]
        last_dep = conn.execute(
            "SELECT MAX(departure_time) AS t FROM departures WHERE route_id = %s", (route["route_id"],)
        ).fetchone()["t"]
        wait, basis = estimate_wait_minutes(conn, route["route_id"]) if vehicles else (None, 0)
        results.append({
            "route": route,
            "fare": None,
            "vehicles": vehicles,
            "estimated_wait_minutes": wait,
            "wait_basis_departures": basis,
            "last_departure": last_dep,
        })
    return {"results": results, "last_updated": data_last_updated(conn)}


@router.get("/driver/vehicles")
def driver_vehicle_list(conn=Depends(get_conn)):
    """Vehicle numbers for the driver's 'select your vehicle' list (no driver names or phone numbers)."""
    return conn.execute(
        "SELECT vehicle_id, registration_number FROM vehicles WHERE vehicle_status <> 'unavailable' "
        "ORDER BY registration_number"
    ).fetchall()


@router.get("/driver/turn")
def driver_turn(
    vehicle_id: Optional[int] = Query(None),
    registration_number: Optional[str] = Query(None, max_length=20),
    conn=Depends(get_conn),
):
    """Tells a driver where their vehicle is in the queue and whether it is their turn to load."""
    if vehicle_id is None and not registration_number:
        raise ApiError(422, "Provide vehicle_id or registration_number")
    if vehicle_id is not None:
        v = conn.execute("SELECT vehicle_id, registration_number, route_id FROM vehicles WHERE vehicle_id = %s",
                         (vehicle_id,)).fetchone()
    else:
        v = conn.execute(
            "SELECT vehicle_id, registration_number, route_id FROM vehicles WHERE upper(registration_number) = upper(%s)",
            (registration_number.strip(),),
        ).fetchone()
    if not v:
        raise ApiError(404, "Vehicle not found")

    entry = conn.execute(
        f"SELECT queue_position, queue_status, station_id FROM vehicle_queue "
        f"WHERE vehicle_id = %s AND queue_status IN {ACTIVE_SQL}",
        (v["vehicle_id"],),
    ).fetchone()
    info = {
        "vehicle_id": v["vehicle_id"],
        "registration_number": v["registration_number"],
        "in_queue": entry is not None,
        "queue_position": entry["queue_position"] if entry else None,
        "vehicles_ahead": entry["queue_position"] - 1 if entry else None,
        "is_my_turn": bool(entry and entry["queue_position"] == 1),
        "queue_status": entry["queue_status"] if entry else None,
        "last_updated": data_last_updated(conn),
    }
    return info


@router.get("/sync/download")
def sync_download(since: Optional[str] = Query(None), conn=Depends(get_conn)):
    """Everything the passenger app needs to keep a saved copy for offline use.
    The data set is small, so this always returns a full snapshot; `since` is accepted for
    compatibility and echoed back. Save `server_time` and show it as 'last synchronised'."""
    from .queue import queue_view  # local import keeps the module graph simple

    server_time = conn.execute("SELECT CURRENT_TIMESTAMP AS t").fetchone()["t"]
    stations = conn.execute("SELECT station_id, station_name, location FROM stations WHERE is_active").fetchall()
    routes = conn.execute(
        """SELECT r.route_id, r.route_name, r.origin, de.destination_name AS destination, r.station_id
           FROM routes r JOIN destinations de ON de.destination_id = r.destination_id
           WHERE r.is_active ORDER BY r.route_name"""
    ).fetchall()
    departures = conn.execute(
        """SELECT dep.departure_id, dep.route_id, dep.vehicle_id, v.registration_number, dep.departure_time
           FROM departures dep JOIN vehicles v ON v.vehicle_id = dep.vehicle_id
           WHERE dep.departure_time >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
           ORDER BY dep.departure_time DESC LIMIT 200"""
    ).fetchall()
    view = queue_view(conn, config.DEFAULT_STATION_ID)
    return {
        "server_time": server_time,
        "since": since,
        "stations": stations,
        "routes": routes,
        "queue": view["queue"],
        "departures": departures,
        "last_updated": view["last_updated"],
    }

@router.post("/passenger/bookings", status_code=201)
def book_seats(
    body: BookingCreate,
    passenger=Depends(current_passenger),
    conn=Depends(get_conn)
):
    """Allow an authenticated commuter to reserve seats."""

    return create_booking(
        conn,
        passenger["passenger_subject"],
        body.vehicle_id,
        body.seats_booked
    )

@router.get("/passenger/bookings")
def get_my_bookings(
    passenger=Depends(current_passenger),
    conn=Depends(get_conn)
):
    """Return bookings belonging to the signed-in commuter."""

    rows = conn.execute(
        """
        SELECT
            b.booking_reference,
            b.vehicle_id,
            v.registration_number,
            b.seats_booked,
            b.booking_status,
            b.booking_time,
            b.cancelled_at
        FROM bookings b
        JOIN vehicles v ON v.vehicle_id = b.vehicle_id
        WHERE b.passenger_subject = %s
        ORDER BY b.booking_time DESC
        """,
        (passenger["passenger_subject"],)
    ).fetchall()

    return {"bookings": rows}

@router.delete("/passenger/bookings/{booking_reference}")
def cancel_my_booking(
    booking_reference: str,
    passenger=Depends(current_passenger),
    conn=Depends(get_conn)
):
    """Allow a commuter to cancel their own booking."""

    return cancel_booking(
        conn,
        passenger["passenger_subject"],
        booking_reference
    )