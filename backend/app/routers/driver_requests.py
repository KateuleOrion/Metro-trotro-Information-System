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
from ..services import audit, find_or_create_route, normalize_phone, set_seats

router = APIRouter(prefix="/driver/requests", tags=["Driver registration requests"])

REQUEST_SQL = """
SELECT dr.request_id, dr.full_name, dr.phone_number, dr.registration_number, dr.destination, dr.capacity,
       dr.request_status, dr.reject_reason, dr.submitted_at, dr.reviewed_at, dr.driver_id, dr.vehicle_id,
       dr.account_id, dr.existing_driver_id, s.full_name AS reviewed_by_name
FROM driver_requests dr
LEFT JOIN staff s ON s.staff_id = dr.reviewed_by
"""


def _plate_taken(conn, plate: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM vehicles WHERE upper(registration_number) = upper(%s)", (plate,)
    ).fetchone() is not None


def _phone_registered(conn, phone: str) -> bool:
    return conn.execute("SELECT 1 FROM drivers WHERE phone_number = %s", (phone,)).fetchone() is not None


# ---------------------------------------------------------------- driver registers a login
def create_driver_account(conn, body, phone: str, password_hash: str) -> dict:
    """Called by POST /auth/register when role is 'driver' (the same form mates and staff use).
    Creates a pending login account and a driver request linked to it. Approving the request on the
    Drivers tab creates the driver (and vehicle) and switches the login on.
    A driver who is already in the system but has no login yet registers the same way: approving
    links the login to their existing driver record."""
    existing = conn.execute(
        "SELECT driver_id, account_id FROM drivers WHERE phone_number = %s", (phone,)
    ).fetchone()
    if existing and existing["account_id"]:
        raise ApiError(409, "This driver already has an account. Please log in instead")
    if conn.execute(
        "SELECT 1 FROM driver_requests WHERE phone_number = %s AND request_status = 'pending'", (phone,)
    ).fetchone():
        raise ApiError(409, "You already have a request waiting for the station manager")
    plate = body.registration_number.upper() if body.registration_number else None
    if plate and _plate_taken(conn, plate):
        raise ApiError(409, "A vehicle with this registration number is already registered")
    email = body.email.lower() if body.email else None
    taken = conn.execute(
        "SELECT staff_id, role, account_status FROM staff WHERE phone_number = %s"
        + (" OR lower(email) = %s" if email else ""), (phone, email) if email else (phone,)
    ).fetchall()
    retry = [a for a in taken if a["role"] == "driver" and a["account_status"] == "rejected"]
    if len(taken) != len(retry):
        raise ApiError(409, "An account with this phone number already exists. Please log in instead")
    try:
        if retry:  # registering again after a rejection: reuse the old login with the new details
            account = conn.execute(
                "UPDATE staff SET full_name = %s, email = %s, password_hash = %s, account_status = 'pending', "
                "reject_reason = NULL, reviewed_by = NULL, reviewed_at = NULL WHERE staff_id = %s RETURNING staff_id",
                (body.full_name, email, password_hash, retry[0]["staff_id"]),
            ).fetchone()
        else:
            account = conn.execute(
                "INSERT INTO staff (full_name, email, phone_number, password_hash, role, account_status) "
                "VALUES (%s, %s, %s, %s, 'driver', 'pending') RETURNING staff_id",
                (body.full_name, email, phone, password_hash),
            ).fetchone()
        req = conn.execute(
            "INSERT INTO driver_requests (full_name, phone_number, registration_number, destination, capacity, "
            "station_id, account_id, existing_driver_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING request_id",
            (body.full_name, phone, plate, body.destination, body.capacity, config.DEFAULT_STATION_ID,
             account["staff_id"], existing["driver_id"] if existing else None),
        ).fetchone()
    except pg.UniqueViolation:
        raise ApiError(409, "An account with this phone number already exists. Please log in instead")
    audit(conn, account["staff_id"], "DRIVER_REGISTERED", "driver_requests", req["request_id"])
    return {"account_status": "pending", "staff_id": account["staff_id"], "request_id": req["request_id"],
            "message": "Account created. The station manager must approve it before you can log in"}


# ---------------------------------------------------------------- driver side (public)
@router.post("", status_code=201)
def submit_request(body: DriverRequestIn, conn=Depends(get_conn, scope="function")):
    """A driver asks to be registered at the station (sign up in the driver app)."""
    phone = normalize_phone(body.phone_number)  # '+233 24 123 4567' and '0241234567' are one number
    if _phone_registered(conn, phone):
        raise ApiError(409, "A driver with this phone number is already registered")
    if conn.execute(
        "SELECT 1 FROM driver_requests WHERE phone_number = %s AND request_status = 'pending'", (phone,)
    ).fetchone():
        raise ApiError(409, "You already have a request waiting for the station manager")
    plate = body.registration_number.upper() if body.registration_number else None
    if plate and _plate_taken(conn, plate):
        raise ApiError(409, "A vehicle with this registration number is already registered")
    try:
        row = conn.execute(
            "INSERT INTO driver_requests (full_name, phone_number, registration_number, destination, capacity, station_id) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING request_id, request_status, submitted_at",
            (body.full_name, phone, plate, body.destination, body.capacity, config.DEFAULT_STATION_ID),
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
        (normalize_phone(phone),),
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
    if req["existing_driver_id"]:
        # A driver already in the system registered a login: link it to their record.
        driver = conn.execute(
            "SELECT driver_id, account_id FROM drivers WHERE driver_id = %s FOR UPDATE", (req["existing_driver_id"],)
        ).fetchone()
        if not driver or driver["account_id"]:
            raise ApiError(409, "This driver already has an account. Reject this request instead")
    elif _phone_registered(conn, req["phone_number"]):
        raise ApiError(409, "A driver with this phone number is already registered. Reject this request instead")
    if req["registration_number"] and _plate_taken(conn, req["registration_number"]):
        raise ApiError(409, "A vehicle with this registration number is already registered. Reject this request instead")

    if not req["existing_driver_id"]:
        driver = conn.execute(
            "INSERT INTO drivers (driver_name, phone_number) VALUES (%s, %s) RETURNING driver_id",
            (req["full_name"], req["phone_number"]),
        ).fetchone()
        audit(conn, staff["staff_id"], "DRIVER_CREATED", "drivers", driver["driver_id"], {"request_id": request_id})
    if req["account_id"]:
        # Switch on the driver's login and link it to the driver record.
        conn.execute(
            "UPDATE staff SET account_status = 'active', reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP "
            "WHERE staff_id = %s AND role = 'driver'", (staff["staff_id"], req["account_id"]),
        )
        conn.execute("UPDATE drivers SET account_id = %s WHERE driver_id = %s", (req["account_id"], driver["driver_id"]))

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
    req = _pending(conn, request_id)
    conn.execute(
        "UPDATE driver_requests SET request_status = 'rejected', reject_reason = %s, reviewed_by = %s, "
        "reviewed_at = CURRENT_TIMESTAMP WHERE request_id = %s",
        (body.reason or None, staff["staff_id"], request_id),
    )
    if req["account_id"]:  # the driver's login stays off
        conn.execute(
            "UPDATE staff SET account_status = 'rejected', reject_reason = %s, reviewed_by = %s, "
            "reviewed_at = CURRENT_TIMESTAMP WHERE staff_id = %s AND role = 'driver'",
            (body.reason or None, staff["staff_id"], req["account_id"]),
        )
    audit(conn, staff["staff_id"], "DRIVER_REQUEST_REJECTED", "driver_requests", request_id,
          {"reason": body.reason} if body.reason else None)
    return conn.execute(REQUEST_SQL + " WHERE dr.request_id = %s", (request_id,)).fetchone()
