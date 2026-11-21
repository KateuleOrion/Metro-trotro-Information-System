# Sync backend

## Setup
1. `npm install`
2. Copy `.env.example` to `.env` and fill it in
3. Run `schema.sql` in PostgreSQL (or adapt it to the database developer's tables)
4. `npm start`

## Endpoints (all need `Authorization: Bearer <token>`)

### POST /sync/upload
Body: `{ "device_id": "...", "records": [ ... ] }`
Response: `{ "synced": ["uuid"], "failed": [{ "client_uuid": "...", "reason": "..." }] }`

### GET /sync/download?since=<ISO time>
Response: `{ "server_time", "routes", "stations", "departures", "deleted_ids" }`
The app saves `server_time` and sends it as `since` on the next sync.

## Notes for the team
- `failed` is a list of objects (uuid + reason), not just ids, so the app can show why.
- Staff identity comes from the token. `staff_id` in the body is ignored.
- Login is not included. The token must contain `staff_id` and be signed with JWT_SECRET.
