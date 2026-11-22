import Dexie from "dexie";

// Local browser database for the station staff dashboard.
// outbox: every action staff record, kept until the server confirms it.
export const db = new Dexie("metro_trotro_staff");

db.version(1).stores({
  outbox: "client_uuid, status, recorded_at, type",
});
