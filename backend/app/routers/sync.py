"""Offline synchronisation: staff devices upload what they recorded without internet.

Each record has a client_uuid, so sending the same record twice is safe (it is applied once).
Records are applied oldest-first, each one on its own, so one bad record does not block the rest.
"""
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import APIRouter, Depends
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from .. import config
from ..db import get_conn
from ..errors import ApiError
from ..schemas import SyncBatchIn, SyncRecord
from ..security import current_staff
from ..services import data_last_updated, get_vehicle, record_arrival, record_departure, reorder_queue

router = APIRouter(prefix="/sync", tags=["Offline sync"])


def _readable(err: ValidationError) -> str:
    first = err.errors()[0]
    where = ".".join(str(p) for p in first["loc"])
    return f"{where}: {first['msg']}" if where else first["msg"]


def _apply(conn, staff_id: int, rec: SyncRecord):
    if rec.recorded_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ApiError(422, "recorded_at is in the future")
    if rec.type in ("vehicle_arrival", "vehicle_departure"):
        if rec.vehicle_id is None:
            raise ApiError(422, "vehicle_id is required")
        vehicle = get_vehicle(conn, rec.vehicle_id)
        if rec.station_id is not None and rec.station_id != vehicle["station_id"]:
            raise ApiError(422, "station_id does not match the vehicle's station")
        action = record_arrival if rec.type == "vehicle_arrival" else record_departure
        action(conn, staff_id, rec.vehicle_id, when=rec.recorded_at)
    else:  # queue_update: payload {"vehicle_ids": [...]} in the new order
        ids = rec.payload.get("vehicle_ids")
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            raise ApiError(422, "payload.vehicle_ids must be a list of vehicle ids")
        reorder_queue(conn, staff_id, rec.station_id or config.DEFAULT_STATION_ID, ids)


def _save_result(conn, staff_id: int, rec: SyncRecord, ok: bool, error):
    conn.execute(
        """INSERT INTO offline_records
               (record_id, staff_id, record_type, data_payload, creation_time, sync_status, synced_at, error_message)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (record_id) DO UPDATE SET
               sync_status = EXCLUDED.sync_status, synced_at = EXCLUDED.synced_at,
               error_message = EXCLUDED.error_message""",
        (str(rec.client_uuid), staff_id, rec.type, Jsonb(rec.model_dump(mode="json")), rec.recorded_at,
         "S" if ok else "F", datetime.now(timezone.utc) if ok else None, None if ok else error),
    )


@router.post("/batch")
@router.post("/upload")  # the name used by the first version of the sync backend
def upload(body: SyncBatchIn, staff=Depends(current_staff), conn=Depends(get_conn)):
    staff_id = staff["staff_id"]  # always taken from the token, never from the request body
    synced, failed, valid = [], [], []

    for raw in body.records:
        try:
            rec = SyncRecord.model_validate(raw)
            if rec.recorded_at.tzinfo is None:
                rec = rec.model_copy(update={"recorded_at": rec.recorded_at.replace(tzinfo=timezone.utc)})
            valid.append(rec)
        except ValidationError as err:
            uid = raw.get("client_uuid") if isinstance(raw, dict) else None
            msg = _readable(err)
            failed.append({"client_uuid": uid, "error": msg, "reason": msg})

    for rec in sorted(valid, key=lambda r: r.recorded_at):
        uid = str(rec.client_uuid)
        existing = conn.execute("SELECT sync_status FROM offline_records WHERE record_id = %s", (uid,)).fetchone()
        if existing and existing["sync_status"] == "S":
            synced.append(uid)  # already applied earlier: confirm again so the device stops retrying
            continue
        try:
            with conn.transaction():  # a failed record is undone without affecting the others
                _apply(conn, staff_id, rec)
                _save_result(conn, staff_id, rec, True, None)
            synced.append(uid)
        except ApiError as err:
            _save_result(conn, staff_id, rec, False, err.detail)
            failed.append({"client_uuid": uid, "error": err.detail, "reason": err.detail})
        except psycopg.Error:
            _save_result(conn, staff_id, rec, False, "Server error saving record")
            failed.append({"client_uuid": uid, "error": "Server error saving record",
                           "reason": "Server error saving record"})

    return {"synced": synced, "failed": failed, "last_updated": data_last_updated(conn)}
