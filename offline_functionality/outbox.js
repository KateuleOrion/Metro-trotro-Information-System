import { db } from "./db";

export const RECORD_TYPES = ["vehicle_arrival", "queue_update", "vehicle_departure"];

// Status values: "pending" (not sent yet), "failed" (last attempt failed, will retry), "synced" (server confirmed)

export async function addRecord({ type, station_id, vehicle_id, staff_id, payload = {} }) {
  if (!RECORD_TYPES.includes(type)) throw new Error(`Unknown record type: ${type}`);
  if (!station_id || !vehicle_id || !staff_id) {
    throw new Error("station_id, vehicle_id and staff_id are required");
  }
  const record = {
    client_uuid: crypto.randomUUID(), // needs https or localhost
    type,
    station_id,
    vehicle_id,
    staff_id,
    payload,
    recorded_at: new Date().toISOString(), // time the staff member acted, not the sync time
    status: "pending",
    attempts: 0,
    last_error: null,
  };
  await db.outbox.add(record);
  return record;
}

// Oldest first, so the server sees events in the order they happened.
export async function getPending() {
  const rows = await db.outbox.where("status").anyOf("pending", "failed").toArray();
  return rows.sort((a, b) => a.recorded_at.localeCompare(b.recorded_at));
}

export async function markSynced(uuids) {
  const now = new Date().toISOString();
  await db.outbox.bulkUpdate(uuids.map((k) => ({ key: k, changes: { status: "synced", synced_at: now, last_error: null } })));
}

// items: [{ client_uuid, error }]
export async function markFailed(items) {
  for (const { client_uuid, error } of items) {
    const row = await db.outbox.get(client_uuid);
    if (!row) continue;
    await db.outbox.update(client_uuid, {
      status: "failed",
      attempts: row.attempts + 1,
      last_error: String(error ?? "unknown error"),
    });
  }
}

export async function countByStatus() {
  const counts = { pending: 0, failed: 0, synced: 0 };
  await db.outbox.each((r) => { counts[r.status] += 1; });
  return counts;
}
