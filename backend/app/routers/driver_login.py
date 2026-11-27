"""Driver login for the driver app.

New drivers sign up by sending a registration request (driver_requests.py). An existing,
approved driver logs in with only their phone number: no password.
"""
from fastapi import APIRouter, Depends
from pydantic import Field

from ..db import get_conn
from ..errors import ApiError
from ..schemas import Base
from ..services import normalize_phone

router = APIRouter(prefix="/driver", tags=["Driver login"])


class DriverLoginIn(Base):
    phone_number: str = Field(pattern=r"^\+?[0-9][0-9 -]{6,19}$")


@router.post("/login")
def driver_login(body: DriverLoginIn, conn=Depends(get_conn, scope="function")):
    phone = normalize_phone(body.phone_number)
    driver = conn.execute(
        "SELECT driver_id, driver_name, phone_number FROM drivers WHERE phone_number = %s", (phone,)
    ).fetchone()

    if not driver:
        # Not registered yet: say whether a request is waiting or was rejected.
        req = conn.execute(
            "SELECT request_status, reject_reason FROM driver_requests WHERE phone_number = %s "
            "ORDER BY submitted_at DESC, request_id DESC LIMIT 1", (phone,)
        ).fetchone()
        if req and req["request_status"] == "pending":
            raise ApiError(403, "Your registration is waiting for the station manager's approval")
        if req and req["request_status"] == "rejected":
            reason = f" Reason: {req['reject_reason']}" if req["reject_reason"] else ""
            raise ApiError(403, f"Your registration was not approved.{reason} You can sign up again")
        raise ApiError(404, "No driver is registered with this phone number. Please sign up")

    vehicles = conn.execute(
        "SELECT v.vehicle_id, v.registration_number, r.route_name, d.destination_name AS destination "
        "FROM vehicles v LEFT JOIN routes r ON r.route_id = v.route_id "
        "LEFT JOIN destinations d ON d.destination_id = r.destination_id "
        "WHERE v.driver_id = %s ORDER BY v.registration_number", (driver["driver_id"],)
    ).fetchall()
    return {
        "driver_id": driver["driver_id"],
        "full_name": driver["driver_name"],
        "phone_number": driver["phone_number"],
        "vehicles": vehicles,
    }
