from fastapi import APIRouter, Depends
from psycopg import errors as pg

from ..db import get_conn
from ..errors import ApiError
from ..schemas import VehicleCreate, VehicleUpdate
from ..security import current_staff, require_manager
from ..services import audit, data_last_updated, set_seats, update_vehicle, vehicle_rows

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.get("")
def list_vehicles(staff=Depends(current_staff), conn=Depends(get_conn)):
    return {"vehicles": vehicle_rows(conn), "last_updated": data_last_updated(conn)}


@router.post("", status_code=201)
def create_vehicle(body: VehicleCreate, staff=Depends(require_manager), conn=Depends(get_conn)):
    seats = body.available_seats if body.available_seats is not None else body.capacity
    if seats > body.capacity:
        raise ApiError(422, f"Seats available cannot exceed the vehicle's capacity ({body.capacity})")
    try:
        row = conn.execute(
            "INSERT INTO vehicles (registration_number, route_id, capacity, driver_id) VALUES (%s, %s, %s, %s) "
            "RETURNING vehicle_id",
            (body.registration_number.upper(), body.route_id, body.capacity, body.driver_id),
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
def edit_vehicle(vehicle_id: int, body: VehicleUpdate, staff=Depends(current_staff), conn=Depends(get_conn)):
    changes = {k: getattr(body, k) for k in body.model_fields_set}
    if not changes:
        raise ApiError(422, "Nothing to update")
    try:
        update_vehicle(conn, staff["staff_id"], vehicle_id, changes)
    except pg.ForeignKeyViolation:
        raise ApiError(422, "Unknown route or driver")
    return vehicle_rows(conn, vehicle_id)[0]
