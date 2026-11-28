"""The driver's own app. A driver logs in with the same login as mates and station staff
(POST /auth/login) and can then only read their own vehicles and their place in the queue."""
from fastapi import APIRouter, Depends

from ..db import get_conn
from ..errors import ApiError
from ..security import current_staff
from ..services import ACTIVE_SQL, data_last_updated, vehicle_rows
from .tracking import _f, describe

router = APIRouter(prefix="/driver", tags=["Driver app"])


def require_driver(account: dict = Depends(current_staff)) -> dict:
    if account["role"] != "driver":
        raise ApiError(403, "Only drivers can open the driver app")
    return account


@router.get("/me")
def my_vehicles(account=Depends(require_driver), conn=Depends(get_conn, scope="function")):
    """The signed-in driver, their vehicles, seats free, each vehicle's place in the queue, and for the
    map: where the vehicle is, its destination, distance, direction and ETA (same rules as the live map)."""
    now = conn.execute("SELECT CURRENT_TIMESTAMP AS t").fetchone()["t"]
    driver = conn.execute(
        "SELECT driver_id, driver_name, phone_number FROM drivers WHERE account_id = %s", (account["staff_id"],)
    ).fetchone()
    if not driver:
        raise ApiError(404, "Your login is not linked to a driver yet. Please contact the station manager")
    vehicles = []
    for row in conn.execute(
        "SELECT vehicle_id FROM vehicles WHERE driver_id = %s ORDER BY registration_number", (driver["driver_id"],)
    ).fetchall():
        v = vehicle_rows(conn, row["vehicle_id"])[0]
        entry = conn.execute(
            f"SELECT queue_position, queue_status FROM vehicle_queue "
            f"WHERE vehicle_id = %s AND queue_status IN {ACTIVE_SQL}", (row["vehicle_id"],)
        ).fetchone()
        dest = conn.execute(
            "SELECT de.destination_name, de.latitude, de.longitude FROM vehicles ve "
            "JOIN routes r ON r.route_id = ve.route_id JOIN destinations de ON de.destination_id = r.destination_id "
            "WHERE ve.vehicle_id = %s", (row["vehicle_id"],)
        ).fetchone()
        history = conn.execute(
            "SELECT latitude, longitude, speed_kmh, recorded_at FROM vehicle_positions "
            "WHERE vehicle_id = %s ORDER BY recorded_at DESC, position_id DESC LIMIT 30", (row["vehicle_id"],)
        ).fetchall()
        dest_lat, dest_lon = (_f(dest["latitude"]), _f(dest["longitude"])) if dest else (None, None)
        v["map"] = {
            "destination": dest["destination_name"] if dest else None,
            "destination_latitude": dest_lat,
            "destination_longitude": dest_lon,
            "latitude": float(history[0]["latitude"]) if history else None,
            "longitude": float(history[0]["longitude"]) if history else None,
            "recorded_at": history[0]["recorded_at"] if history else None,
            **(describe(history, dest_lat, dest_lon, now) if history else {}),
        }
        v.update({
            "in_queue": entry is not None,
            "queue_position": entry["queue_position"] if entry else None,
            "vehicles_ahead": entry["queue_position"] - 1 if entry else None,
            "is_my_turn": bool(entry and entry["queue_position"] == 1),
            "queue_status": entry["queue_status"] if entry else None,
        })
        vehicles.append(v)
    station = conn.execute(
        "SELECT station_name, latitude, longitude FROM stations WHERE is_active ORDER BY station_id LIMIT 1"
    ).fetchone()
    return {
        "station": station and {"name": station["station_name"], "latitude": _f(station["latitude"]),
                                "longitude": _f(station["longitude"])},
        "driver_id": driver["driver_id"],
        "full_name": driver["driver_name"],
        "phone_number": driver["phone_number"],
        "vehicles": vehicles,
        "last_updated": data_last_updated(conn),
    }
