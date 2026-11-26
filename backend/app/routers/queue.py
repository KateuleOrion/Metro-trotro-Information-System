from typing import Optional

from fastapi import APIRouter, Depends, Query

from .. import config
from ..db import get_conn
from ..schemas import QueueOrderIn, VehicleRef
from ..security import current_staff
from ..services import (
    ACTIVE_SQL, LATEST_SEATS_JOIN, data_last_updated, record_arrival, record_departure,
    remove_from_queue, reorder_queue,
)

router = APIRouter(prefix="/queue", tags=["Queue"])


def queue_view(conn, station_id: int) -> dict:
    """The queue as passengers and staff see it. Driver names and phone numbers are not included."""
    rows = conn.execute(
        f"""SELECT q.queue_id, q.queue_position AS position, q.arrival_time, q.queue_status, q.last_updated,
                   v.vehicle_id, v.registration_number, v.capacity, v.vehicle_status, seat.available_seats,
                   r.route_id, r.route_name, de.destination_name AS destination
            FROM vehicle_queue q
            JOIN vehicles v ON v.vehicle_id = q.vehicle_id
            JOIN routes r ON r.route_id = v.route_id
            JOIN destinations de ON de.destination_id = r.destination_id
            {LATEST_SEATS_JOIN}
            WHERE q.station_id = %s AND q.queue_status IN {ACTIVE_SQL}
            ORDER BY q.queue_position""",
        (station_id,),
    ).fetchall()
    queue = [
        {
            "queue_id": r["queue_id"], "position": r["position"], "arrival_time": r["arrival_time"],
            "queue_status": r["queue_status"],
            "vehicle": {
                "vehicle_id": r["vehicle_id"], "registration_number": r["registration_number"],
                "capacity": r["capacity"], "available_seats": r["available_seats"],
                "vehicle_status": r["vehicle_status"], "route_name": r["route_name"],
                "destination": r["destination"],
            },
        }
        for r in rows
    ]
    return {"queue": queue, "last_updated": data_last_updated(conn)}


@router.get("")
def get_queue(station_id: Optional[int] = Query(None), conn=Depends(get_conn, scope="function")):
    return queue_view(conn, station_id or config.DEFAULT_STATION_ID)


@router.post("/arrivals", status_code=201)
def arrival(body: VehicleRef, staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    row = record_arrival(conn, staff["staff_id"], body.vehicle_id)
    return {"queue_id": row["queue_id"], "queue_position": row["queue_position"], "arrived_at": row["arrival_time"],
            "last_updated": data_last_updated(conn)}


@router.put("/order")
def order(body: QueueOrderIn, staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    reorder_queue(conn, staff["staff_id"], body.station_id or config.DEFAULT_STATION_ID, body.vehicle_ids)
    return {"ok": True, "last_updated": data_last_updated(conn)}


@router.post("/departures", status_code=201)
def departure(body: VehicleRef, staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    dep = record_departure(conn, staff["staff_id"], body.vehicle_id)
    return {"departure_id": dep["departure_id"], "departed_at": dep["departure_time"],
            "last_updated": data_last_updated(conn)}


@router.post("/cancel")
def cancel(body: VehicleRef, staff=Depends(current_staff), conn=Depends(get_conn, scope="function")):
    remove_from_queue(conn, staff["staff_id"], body.vehicle_id)
    return {"ok": True, "last_updated": data_last_updated(conn)}
