import { getPending, markSynced, markFailed } from "./outbox";
import { mockSyncBatch } from "./mockApi";

const USE_MOCK = true;                    // set to false once the backend is ready
const API_BASE = "http://localhost:8000"; // FastAPI address from the backend teammate
const BATCH_SIZE = 50;

let running = false;

async function sendBatch(device_id, records) {
  if (USE_MOCK) return mockSyncBatch({ device_id, records });
  const res = await fetch(`${API_BASE}/sync/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }, // add the staff auth token here
    body: JSON.stringify({ device_id, records }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json(); // { synced: [uuid...], failed: [{client_uuid, error}...] }
}

const toWire = (r) => ({
  client_uuid: r.client_uuid,
  type: r.type,
  station_id: r.station_id,
  vehicle_id: r.vehicle_id,
  staff_id: r.staff_id,
  recorded_at: r.recorded_at,
  payload: r.payload,
});

// Send everything pending. Safe to call repeatedly.
export async function flushOutbox(device_id = "station-01") {
  if (running) return { skipped: "already running" };
  if (!navigator.onLine) return { skipped: "offline" };
  running = true;
  const result = { synced: 0, failed: 0 };
  try {
    const pending = await getPending(); // one snapshot, so failed rows cannot block newer ones
    for (let i = 0; i < pending.length; i += BATCH_SIZE) {
      const batch = pending.slice(i, i + BATCH_SIZE);
      try {
        const res = await sendBatch(device_id, batch.map(toWire));
        await markSynced(res.synced);
        await markFailed(res.failed);
        result.synced += res.synced.length;
        result.failed += res.failed.length;
      } catch (err) {
        // connection dropped mid-sync: keep the records, try again later
        await markFailed(batch.map((r) => ({ client_uuid: r.client_uuid, error: err.message })));
        result.failed += batch.length;
        break;
      }
    }
  } finally {
    running = false;
  }
  return result;
}

// Call once when the dashboard starts. Returns a function that stops auto-sync.
export function startAutoSync(device_id, intervalMs = 30000) {
  const onOnline = () => flushOutbox(device_id);
  window.addEventListener("online", onOnline);
  const timer = setInterval(() => flushOutbox(device_id), intervalMs);
  flushOutbox(device_id);
  return () => {
    window.removeEventListener("online", onOnline);
    clearInterval(timer);
  };
}
