from fastapi import APIRouter, Depends
from psycopg import errors as pg

from ..db import get_conn
from ..errors import ApiError
from ..schemas import SeatChange, VehicleCreate, VehicleUpdate
from ..security import current_staff, require_manager
from ..services import (audit, change_seats, data_last_updated, find_or_create_route, set_seats,
                        update_vehicle, vehicle_rows)

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("")
def list_vehicles(staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    return {"vehicles": vehicle_rows(conn), "last_updated": data_last_updated(conn)}


@router.post("", status_code=201)
def create_vehicle(body: VehicleCreate, staff=Depends(require_manager), conn=Depends(get_conn, scope="function")):
    seats = body.available_seats if body.available_seats is not None else body.capacity
    if seats > body.capacity:
        raise ApiError(422, f"Seats available cannot exceed the vehicle's capacity ({body.capacity})")
    # Check the registration number first, so a duplicate does not create a new driver or route.
    if conn.execute("SELECT 1 FROM vehicles WHERE upper(registration_number) = upper(%s)",
                    (body.registration_number,)).fetchone():
        raise ApiError(409, "A vehicle with this registration number already exists")
    # A typed-in destination is looked up and its route created here if it does not exist yet.
    # The driver must already be registered (approved through a driver registration request).
    route_id = body.route_id
    if route_id is None:
        route_id = find_or_create_route(conn, staff["staff_id"], body.destination)
    driver_id = body.driver_id
    try:
        row = conn.execute(
            "INSERT INTO vehicles (registration_number, route_id, capacity, driver_id) VALUES (%s, %s, %s, %s) "
            "RETURNING vehicle_id",
            (body.registration_number.upper(), route_id, body.capacity, driver_id),
        ).fetchone()
    except pg.UniqueViolation:
        raise ApiError(409, "A vehicle with this registration number already exists")
    except pg.ForeignKeyViolation:
        raise ApiError(422, "Unknown route or driver")
    set_seats(conn, staff["staff_id"], row["vehicle_id"], body.capacity, seats)
    audit(conn, staff["staff_id"], "VEHICLE_CREATED", "vehicles", row["vehicle_id"],
          {"registration_number": body.registration_number.upper()})
    return vehicle_rows(conn, row["vehicle_id"])[0]


@router.put("/{vehicle_id}")
def edit_vehicle(vehicle_id: int, body: VehicleUpdate, staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    changes = {k: getattr(body, k) for k in body.model_fields_set}
    if not changes:
        raise ApiError(422, "Nothing to update")
    try:
        update_vehicle(conn, staff["staff_id"], vehicle_id, changes)
    except pg.ForeignKeyViolation:
        raise ApiError(422, "Unknown route or driver")
    return vehicle_rows(conn, vehicle_id)[0]


@router.post("/{vehicle_id}/book-seats")
def book_seats(vehicle_id: int, body: SeatChange, staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    """Mate books `count` passengers onto the vehicle. Refused if fewer seats are left."""
    change_seats(conn, staff["staff_id"], vehicle_id, -body.count)
    return vehicle_rows(conn, vehicle_id)[0]


@router.post("/{vehicle_id}/release-seats")
def release_seats(vehicle_id: int, body: SeatChange, staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    """Mate cancels `count` bookings (a passenger got off or changed their mind)."""
    change_seats(conn, staff["staff_id"], vehicle_id, body.count)
    return vehicle_rows(conn, vehicle_id)[0]
