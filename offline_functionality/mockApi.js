// Fake backend so the offline work can be built and tested before folder 2 is ready.
// Replace by setting USE_MOCK = false in syncService.js.

const seen = new Set(); // client_uuids the "server" has already stored
let failureRate = 0;    // 0..1, to simulate a flaky connection
let down = false;       // simulate the server being unreachable

export function setMockFailureRate(rate) { failureRate = rate; }
export function setMockServerDown(isDown) { down = isDown; }
export function resetMockServer() { seen.clear(); failureRate = 0; down = false; }
export function mockStoredCount() { return seen.size; }

export async function mockSyncBatch({ device_id, records }) {
  await new Promise((r) => setTimeout(r, 50)); // pretend network delay
  if (down) throw new Error("Network error");
  const synced = [];
  const failed = [];
  for (const rec of records) {
    if (Math.random() < failureRate) {
      failed.push({ client_uuid: rec.client_uuid, error: "Server rejected record" });
      continue;
    }
    seen.add(rec.client_uuid); // a Set means a duplicate is stored once (idempotent)
    synced.push(rec.client_uuid);
  }
  return { synced, failed };
}
