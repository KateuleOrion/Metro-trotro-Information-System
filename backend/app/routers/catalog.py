"""Routes (public to read) and drivers (staff only: they contain phone numbers)."""
from fastapi import APIRouter, Depends
from psycopg import errors as pg

from ..db import get_conn
from ..errors import ApiError
from .. import config
from ..schemas import RouteCreate
from ..security import current_staff, require_manager
from ..services import audit

router = APIRouter(tags=["Routes and drivers"])

ROUTE_SQL = """
SELECT r.route_id, r.route_name, r.origin, r.destination_id, d.destination_name AS destination, r.station_id
FROM routes r JOIN destinations d ON d.destination_id = r.destination_id
"""


@router.get("/routes")
def list_routes(conn=Depends(get_conn, scope="function")):
    return conn.execute(ROUTE_SQL + " WHERE r.is_active ORDER BY r.route_name").fetchall()


@router.post("/routes", status_code=201)
def create_route(body: RouteCreate, staff=Depends(require_manager), conn=Depends(get_conn, scope="function")):
    station_id = body.station_id or config.DEFAULT_STATION_ID
    station = conn.execute("SELECT station_name FROM stations WHERE station_id = %s AND is_active", (station_id,)).fetchone()
    if not station:
        raise ApiError(404, "Station not found")
    dest = conn.execute(
        "SELECT destination_id FROM destinations WHERE lower(destination_name) = lower(%s)", (body.destination,)
    ).fetchone()
    if not dest:
        dest = conn.execute(
            "INSERT INTO destinations (destination_name) VALUES (%s) RETURNING destination_id", (body.destination,)
        ).fetchone()
    origin = body.origin or station["station_name"]
    route_name = body.route_name or f"{origin} - {body.destination}"
    try:
        row = conn.execute(
            "INSERT INTO routes (route_name, origin, destination_id, station_id) VALUES (%s, %s, %s, %s) "
            "RETURNING route_id",
            (route_name, origin, dest["destination_id"], station_id),
        ).fetchone()
    except pg.UniqueViolation:
        raise ApiError(409, "A route with this name already exists at this station")
    audit(conn, staff["staff_id"], "ROUTE_CREATED", "routes", row["route_id"], {"route_name": route_name})
    return conn.execute(ROUTE_SQL + " WHERE r.route_id = %s", (row["route_id"],)).fetchone()


@router.get("/drivers")
def list_drivers(staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    return conn.execute("SELECT driver_id, driver_name, phone_number FROM drivers ORDER BY driver_name").fetchall()

# New drivers are not added here: they send a registration request (see driver_requests.py)
# and are created when the station manager approves it.
