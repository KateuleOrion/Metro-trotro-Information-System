const express = require('express');
const pool = require('./db');
const { requireAuth } = require('./auth');

const router = express.Router();
router.use(requireAuth);

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Returns an error message, or null if the record is valid.
function validateRecord(r) {
  if (!r || typeof r !== 'object') return 'Record must be an object';
  if (!UUID_REGEX.test(r.client_uuid || '')) return 'Invalid client_uuid';
  if (r.type !== 'vehicle_arrival') return 'Unsupported record type';
  if (!Number.isInteger(r.station_id)) return 'station_id must be an integer';
  if (!Number.isInteger(r.vehicle_id)) return 'vehicle_id must be an integer';
  if (!r.recorded_at || isNaN(Date.parse(r.recorded_at)))
    return 'Invalid recorded_at';
  return null;
}

// ---------------------------------------------------------------
// POST /sync/upload
// Receives offline records, saves them, reports synced / failed.
// ---------------------------------------------------------------
router.post('/upload', async (req, res) => {
  const { device_id, records } = req.body || {};

  if (!device_id || !Array.isArray(records)) {
    return res
      .status(400)
      .json({ error: 'device_id and records[] are required' });
  }
  if (records.length > 500) {
    return res.status(400).json({ error: 'Too many records (max 500)' });
  }

  const staffId = req.user.staffId; // from the token, not from the body
  const synced = [];
  const failed = [];

  for (const record of records) {
    const uuid = record && record.client_uuid;
    const problem = validateRecord(record);

    if (problem) {
      failed.push({ client_uuid: uuid || null, reason: problem });
      continue;
    }

    try {
      // ON CONFLICT DO NOTHING: if this client_uuid was already saved
      // (e.g. the device retried after a lost response), we skip the insert
      // but still report it as synced so the device stops retrying.
      await pool.query(
        `INSERT INTO vehicle_arrivals
           (client_uuid, device_id, station_id, vehicle_id, staff_id, recorded_at)
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT (client_uuid) DO NOTHING`,
        [
          record.client_uuid,
          device_id,
          record.station_id,
          record.vehicle_id,
          staffId,
          record.recorded_at,
        ]
      );
      // Only added to "synced" after the database call succeeded.
      synced.push(record.client_uuid);
    } catch (err) {
      console.error('Upload error:', err.message);
      // 23503 = foreign key violation (station/vehicle doesn't exist)
      const reason =
        err.code === '23503'
          ? 'Unknown station_id or vehicle_id'
          : 'Server error saving record';
      failed.push({ client_uuid: uuid, reason });
    }
  }

  res.json({ synced, failed });
});

// ---------------------------------------------------------------
// GET /sync/download?since=2026-11-21T10:00:00Z
// Sends everything changed since the given time.
// No "since" = send everything (first sync).
// ---------------------------------------------------------------
router.get('/download', async (req, res) => {
  const since = req.query.since || '1970-01-01T00:00:00Z';

  if (isNaN(Date.parse(since))) {
    return res.status(400).json({ error: 'Invalid since parameter' });
  }

  try {
    // Take the time BEFORE querying so nothing changed during the
    // query is missed on the next sync.
    const { rows: timeRows } = await pool.query('SELECT now() AS server_time');
    const serverTime = timeRows[0].server_time;

    const [routes, stations, departures, deleted] = await Promise.all([
      pool.query(
        'SELECT * FROM routes WHERE updated_at > $1 AND deleted_at IS NULL',
        [since]
      ),
      pool.query(
        'SELECT * FROM stations WHERE updated_at > $1 AND deleted_at IS NULL',
        [since]
      ),
      pool.query(
        'SELECT * FROM departures WHERE updated_at > $1 AND deleted_at IS NULL',
        [since]
      ),
      pool.query(
        `SELECT 'route' AS type, id FROM routes
           WHERE deleted_at > $1
         UNION ALL
         SELECT 'station', id FROM stations WHERE deleted_at > $1
         UNION ALL
         SELECT 'departure', id FROM departures WHERE deleted_at > $1`,
        [since]
      ),
    ]);

    res.json({
      server_time: serverTime,
      routes: routes.rows,
      stations: stations.rows,
      departures: departures.rows,
      deleted_ids: deleted.rows, // [{ type: 'route', id: 4 }, ...]
    });
  } catch (err) {
    console.error('Download error:', err.message);
    res.status(500).json({ error: 'Could not fetch updates' });
  }
});

module.exports = router;
