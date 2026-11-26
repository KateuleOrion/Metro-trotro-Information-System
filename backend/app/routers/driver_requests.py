"""Driver registration requests.

A driver sends a request to be registered (no sign-in needed). The station manager sees the
waiting requests and approves or rejects each one. Approving creates the driver and, if the
request includes a vehicle, the vehicle too. This is the only way a new driver enters the system.
"""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from psycopg import errors as pg

from .. import config
from ..db import get_conn
from ..errors import ApiError
from ..schemas import DriverRequestIn, RejectIn
from ..security import require_manager
from ..services import audit, find_or_create_route, set_seats

router = APIRouter(prefix="/driver/requests", tags=["Driver registration requests"])

REQUEST_SQL = """
SELECT dr.request_id, dr.full_name, dr.phone_number, dr.registration_number, dr.destination, dr.capacity,
       dr.request_status, dr.reject_reason, dr.submitted_at, dr.reviewed_at, dr.driver_id, dr.vehicle_id,
       s.full_name AS reviewed_by_name
FROM driver_requests dr
LEFT JOIN staff s ON s.staff_id = dr.reviewed_by
"""


def _plate_taken(conn, plate: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM vehicles WHERE upper(registration_number) = upper(%s)", (plate,)
    ).fetchone() is not None


def _phone_registered(conn, phone: str) -> bool:
    return conn.execute("SELECT 1 FROM drivers WHERE phone_number = %s", (phone,)).fetchone() is not None


# ---------------------------------------------------------------- driver side (public)
@router.post("", status_code=201)
def submit_request(body: DriverRequestIn, conn=Depends(get_conn, scope="function")):
    """A driver asks to be registered at the station."""
    if _phone_registered(conn, body.phone_number):
        raise ApiError(409, "A driver with this phone number is already registered")
    if conn.execute(
        "SELECT 1 FROM driver_requests WHERE phone_number = %s AND request_status = 'pending'", (body.phone_number,)
    ).fetchone():
        raise ApiError(409, "You already have a request waiting for the station manager")
    plate = body.registration_number.upper() if body.registration_number else None
    if plate and _plate_taken(conn, plate):
        raise ApiError(409, "A vehicle with this registration number is already registered")
    try:
        row = conn.execute(
            "INSERT INTO driver_requests (full_name, phone_number, registration_number, destination, capacity, station_id) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING request_id, request_status, submitted_at",
            (body.full_name, body.phone_number, plate, body.destination, body.capacity, config.DEFAULT_STATION_ID),
        ).fetchone()
    except pg.UniqueViolation:  # two requests sent at the same moment
        raise ApiError(409, "You already have a request waiting for the station manager")
    audit(conn, None, "DRIVER_REQUEST_SUBMITTED", "driver_requests", row["request_id"])
    return row


@router.get("/status")
def request_status(phone: str = Query(min_length=7, max_length=20), conn=Depends(get_conn, scope="function")):
    """A driver checks what happened to their most recent request, using their phone number."""
    row = conn.execute(
        "SELECT request_id, request_status, reject_reason, submitted_at, reviewed_at "
        "FROM driver_requests WHERE phone_number = %s ORDER BY submitted_at DESC, request_id DESC LIMIT 1",
        (phone.strip(),),
    ).fetchone()
    if not row:
        raise ApiError(404, "No request found for this phone number")
    return row


# ---------------------------------------------------------------- station manager side
@router.get("")
def list_requests(
    status: Literal["pending", "approved", "rejected", "all"] = "pending",
    staff=Depends(require_manager),
    conn=Depends(get_conn, scope="function"),
):
    if status == "all":
        return conn.execute(REQUEST_SQL + " ORDER BY dr.submitted_at DESC").fetchall()
    order = "ASC" if status == "pending" else "DESC"  # oldest waiting request first
    return conn.execute(
        REQUEST_SQL + f" WHERE dr.request_status = %s ORDER BY dr.submitted_at {order}", (status,)
    ).fetchall()


def _pending(conn, request_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM driver_requests WHERE request_id = %s FOR UPDATE", (request_id,)
    ).fetchone()
    if not row:
        raise ApiError(404, "Request not found")
    if row["request_status"] != "pending":
        raise ApiError(409, f"This request has already been {row['request_status']}")
    return row


@router.post("/{request_id}/approve")
def approve_request(request_id: int, staff=Depends(require_manager), conn=Depends(get_conn, scope="function")):
    req = _pending(conn, request_id)
    if _phone_registered(conn, req["phone_number"]):
        raise ApiError(409, "A driver with this phone number is already registered. Reject this request instead")
    if req["registration_number"] and _plate_taken(conn, req["registration_number"]):
        raise ApiError(409, "A vehicle with this registration number is already registered. Reject this request instead")

    driver = conn.execute(
        "INSERT INTO drivers (driver_name, phone_number) VALUES (%s, %s) RETURNING driver_id",
        (req["full_name"], req["phone_number"]),
    ).fetchone()
    audit(conn, staff["staff_id"], "DRIVER_CREATED", "drivers", driver["driver_id"], {"request_id": request_id})

    vehicle_id = None
    if req["registration_number"]:
        route_id = find_or_create_route(conn, staff["staff_id"], req["destination"], req["station_id"])
        vehicle_id = conn.execute(
            "INSERT INTO vehicles (registration_number, route_id, capacity, driver_id) VALUES (%s, %s, %s, %s) "
            "RETURNING vehicle_id",
            (req["registration_number"], route_id, req["capacity"], driver["driver_id"]),
        ).fetchone()["vehicle_id"]
        set_seats(conn, staff["staff_id"], vehicle_id, req["capacity"], req["capacity"])
        audit(conn, staff["staff_id"], "VEHICLE_CREATED", "vehicles", vehicle_id,
              {"registration_number": req["registration_number"], "request_id": request_id})

    conn.execute(
        "UPDATE driver_requests SET request_status = 'approved', reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP, "
        "driver_id = %s, vehicle_id = %s WHERE request_id = %s",
        (staff["staff_id"], driver["driver_id"], vehicle_id, request_id),
    )
    audit(conn, staff["staff_id"], "DRIVER_REQUEST_APPROVED", "driver_requests", request_id)
    return conn.execute(REQUEST_SQL + " WHERE dr.request_id = %s", (request_id,)).fetchone()


@router.post("/{request_id}/reject")
def reject_request(request_id: int, body: RejectIn, staff=Depends(require_manager),
                   conn=Depends(get_conn, scope="function")):
    _pending(conn, request_id)
    conn.execute(
        "UPDATE driver_requests SET request_status = 'rejected', reject_reason = %s, reviewed_by = %s, "
        "reviewed_at = CURRENT_TIMESTAMP WHERE request_id = %s",
        (body.reason or None, staff["staff_id"], request_id),
    )
    audit(conn, staff["staff_id"], "DRIVER_REQUEST_REJECTED", "driver_requests", request_id,
          {"reason": body.reason} if body.reason else None)
    return conn.execute(REQUEST_SQL + " WHERE dr.request_id = %s", (request_id,)).fetchone()
