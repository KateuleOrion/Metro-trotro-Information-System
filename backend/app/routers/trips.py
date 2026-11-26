from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query

from ..db import get_conn
from ..security import current_staff
from ..services import data_last_updated

router = APIRouter(tags=["Trips"])


def _like(text: str) -> str:
    """Turn what the user typed into a safe 'contains' pattern."""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("/trips")
def list_trips(
    destination: str = Query("", max_length=100),
    period: Literal["all", "today", "week", "month"] = "all",
    limit: int = Query(200, ge=1, le=500),
    staff=Depends(current_staff),
    conn=Depends(get_conn, scope="function"),
):
    now = datetime.now(timezone.utc)
    since = {
        "all": None,
        "today": now.replace(hour=0, minute=0, second=0, microsecond=0),
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
    }[period]
    text = destination.strip()
    rows = conn.execute(
        """SELECT dep.departure_id, dep.departure_time, v.registration_number, v.capacity,
                  r.route_name, de.destination_name, dr.driver_name,
                  CASE WHEN seat.available_seats IS NULL THEN NULL
                       ELSE GREATEST(v.capacity - seat.available_seats, 0) END AS passengers
           FROM departures dep
           JOIN vehicles v ON v.vehicle_id = dep.vehicle_id
           JOIN routes r ON r.route_id = dep.route_id
           JOIN destinations de ON de.destination_id = r.destination_id
           LEFT JOIN drivers dr ON dr.driver_id = v.driver_id
           LEFT JOIN LATERAL (
               SELECT sa.available_seats FROM seat_availability sa
               WHERE sa.vehicle_id = dep.vehicle_id AND sa.last_updated <= dep.departure_time
               ORDER BY sa.last_updated DESC, sa.seat_record_id DESC LIMIT 1
           ) seat ON TRUE
           WHERE (%(text)s = '' OR de.destination_name ILIKE %(like)s OR r.route_name ILIKE %(like)s)
             AND (%(since)s::timestamptz IS NULL OR dep.departure_time >= %(since)s::timestamptz)
           ORDER BY dep.departure_time DESC
           LIMIT %(limit)s""",
        {"text": text, "like": _like(text), "since": since, "limit": limit},
    ).fetchall()
    return {"trips": rows, "last_updated": data_last_updated(conn)}
