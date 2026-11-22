// @vitest-environment jsdom
import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it } from "vitest";
import { db } from "../src/offline/db";
import { addRecord, countByStatus } from "../src/offline/outbox";
import { flushOutbox } from "../src/offline/syncService";
import { mockStoredCount, resetMockServer, setMockServerDown } from "../src/offline/mockApi";
import { freshness } from "../src/offline/staleness";

const rec = (type = "vehicle_arrival") => ({ type, station_id: 1, vehicle_id: 7, staff_id: 2 });

beforeEach(async () => {
  await db.outbox.clear();
  resetMockServer();
});

describe("staff outbox", () => {
  it("saves actions locally as pending", async () => {
    await addRecord(rec());
    expect(await countByStatus()).toEqual({ pending: 1, failed: 0, synced: 0 });
  });

  it("rejects invalid input", async () => {
    await expect(addRecord({ ...rec(), type: "nonsense" })).rejects.toThrow();
    await expect(addRecord({ type: "queue_update" })).rejects.toThrow();
  });

  it("syncs all pending records when online", async () => {
    await addRecord(rec());
    await addRecord(rec("queue_update"));
    const res = await flushOutbox();
    expect(res.synced).toBe(2);
    expect(await countByStatus()).toEqual({ pending: 0, failed: 0, synced: 2 });
  });

  it("keeps records and loses none when the connection drops mid-sync", async () => {
    await addRecord(rec());
    setMockServerDown(true);
    await flushOutbox();
    expect((await countByStatus()).failed).toBe(1);
    setMockServerDown(false);
    await flushOutbox();
    expect(await countByStatus()).toEqual({ pending: 0, failed: 0, synced: 1 });
  });

  it("stores a record once even if it is sent twice", async () => {
    const r = await addRecord(rec());
    await flushOutbox();
    await db.outbox.update(r.client_uuid, { status: "pending" }); // force a resend
    await flushOutbox();
    expect(mockStoredCount()).toBe(1);
  });
});

describe("freshness", () => {
  const now = Date.parse("2026-11-21T12:00:00Z");
  const ago = (m) => new Date(now - m * 60000).toISOString();
  it("is fresh, stale, then unavailable", () => {
    expect(freshness(ago(2), now).level).toBe("fresh");
    expect(freshness(ago(25), now).level).toBe("stale");
    expect(freshness(ago(120), now).level).toBe("unavailable");
    expect(freshness(null, now).level).toBe("unavailable");
  });
});
