# Metro Trotro backend (FastAPI + PostgreSQL)

REST API used by the staff dashboard, the passenger app and the offline sync code.
It runs on the team's database file `metro_trotro_db.sql`.

## 1. Set up
```
cd backend
python -m venv venv
venv\Scripts\activate          (Windows)   |   source venv/bin/activate   (Mac/Linux)
pip install -r requirements.txt
```
Create the database and load the schema (the database must use UTF8 encoding):
```
createdb -E UTF8 -T template0 metro_trotro
psql -d metro_trotro -f ../metro_trotro_db.sql
```
**Already have a database from an older `metro_trotro_db.sql`?** It needs the tracking map's tables. Run this
once (it keeps your data and is safe to run twice):
```
psql -d metro_trotro -f ../tracking_migration.sql
psql -d metro_trotro -f ../driver_requests_migration.sql
psql -d metro_trotro -f ../staff_accounts_migration.sql
```
Copy `.env.example` to `.env` and edit it (set your database password and a long random
`JWT_SECRET`). Never commit `.env`.

## 2. Run
```
uvicorn app.main:app --reload --port 8000
```
- Interactive API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Demo logins from the sample data (phone number or email): `0200000001` or `demo@station.com` / `demo123`
  (manager), `0200000002` or `ama@station.com` / `staff123` (station staff). `0200000003` / `staff456` is a
  station staff member waiting for approval. Plain-text sample passwords are replaced by bcrypt hashes
  the first time each account signs in.

## 3. Run the tests
The tests reload the schema before every test, so use a SEPARATE database:
```
createdb -E UTF8 -T template0 metro_trotro_test
set TEST_DATABASE_URL=postgresql://postgres:password@localhost:5432/metro_trotro_test
pytest
```
(Mac/Linux: `export TEST_DATABASE_URL=...`.) The tests find the SQL file at `../metro_trotro_db.sql`
or `../database/metro_trotro_db.sql`, or at the path in `SCHEMA_FILE`.

## Endpoints
| Method and path | Who | Purpose |
|---|---|---|
| POST /auth/login, GET /auth/me | anyone / staff | Sign in (JWT) with `{"login": phone number or email, "password"}` (`{"email": ...}` still works) |
| POST /auth/register | public | Create a `station_staff` or `station_manager` account: `full_name`, `role`, `phone_number` or `email`, `password` (8+ characters). Waits for approval unless `STAFF_SIGNUP_NEEDS_APPROVAL=false` |
| GET /staff/accounts?status=pending\|active\|rejected, POST /staff/accounts/{id}/approve, POST /staff/accounts/{id}/reject | manager | Review new accounts |
| GET /routes, POST /routes | public / manager | Routes |
| GET /drivers | staff | Registered drivers. There is no POST: drivers are added only by approving a request |
| POST /driver/requests, GET /driver/requests/status?phone= | public | A driver asks to be registered (`full_name`, `phone_number`, optional `registration_number` + `destination` + `capacity`) and checks the result |
| GET /driver/me | driver | The signed-in driver's own vehicles, seats free and place in the queue (driver app) |
| GET /driver/requests?status=pending\|approved\|rejected\|all | manager | Driver registration requests (waiting ones oldest first) |
| POST /driver/requests/{id}/approve, POST /driver/requests/{id}/reject | manager | Approve (creates the driver, and the vehicle if one was given) or reject (optional `reason`, shown to the driver) |
| GET /vehicles, POST /vehicles, PUT /vehicles/{id} | staff / manager / staff | Vehicles, seats, status. `POST /vehicles` accepts a typed-in `destination` instead of `route_id` (an existing route is reused, otherwise one is added). The driver must be a registered one, given by `driver_id` |
| GET /tracking/vehicles, GET /tracking/destinations | public | Live map data: position, distance to destination, direction (approaching / moving away / stopped / arrived), ETA |
| POST /tracking/position | staff | Send a vehicle's position (`vehicle_id`, `latitude`, `longitude`, optional `speed_kmh`, `recorded_at`) |
| PUT /tracking/destinations/{id}/location | manager | Set where a destination is on the map |
| GET /queue | public | Current queue |
| POST /queue/arrivals, PUT /queue/order, POST /queue/departures, POST /queue/cancel | staff | Manage the queue |
| GET /trips?destination=&period=all\|today\|week\|month | staff | Departure history |
| GET /passenger/search?from=&to= | public | Passenger vehicle search |
| GET /driver/vehicles, GET /driver/turn | public | Driver view |
| POST /sync/batch, POST /sync/upload, GET /sync/download | staff | Offline synchronisation |
| GET /activity | manager | Audit log |

Every queue change is written to `audit_log`, and queue changes at one station are serialised with a
database lock so two staff members cannot corrupt the order.

## Tracking map: how it works
- Each position report is one row in `vehicle_positions`. Vehicles with no report for 6 hours leave the map.
- Distance is a straight line to the route's destination (the real road distance is longer).
- Direction compares the latest position with an earlier one at least 50 m away. Within 200 m of the destination
  counts as arrived. ETA is only given while approaching at 5 km/h or more.
- A position older than 5 minutes is shown as "No recent signal"; no direction or ETA is claimed for it.
- Position reports are not written to `audit_log` (they arrive every few seconds).

## Before real people use it
1. Make a real secret and put it in `.env` as `JWT_SECRET`:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`. On the real server also set `APP_ENV=production`;
   the server then refuses to start with a weak secret.
2. Replace the demo passwords (demo123 / staff123) for every account:
   `python -m scripts.set_password demo@station.com` (it asks for the new password twice).
3. Never commit `.env`. The `.gitignore` in the main folder already ignores it.

## Staff registration and login: how it works
1. Everyone starts on the dashboard's first screen and chooses Passenger, Driver, Mate, Station staff or Station manager.
   Passengers and mates are pointed to their own phone apps.
2. Station staff or a station manager registers with their phone number (or an email instead) and a password. The
   password is stored as a bcrypt hash. The account starts as `pending`.
3. A station manager approves or rejects it on the Requests tab (Staff accounts). Until then, logging in says
   the account is waiting for approval.
4. They log in with the phone number they registered with (or the email). Phone numbers are matched however
   they are written: `+233 24 123 4567`, `233241234567` and `024-123-4567` are the same number.

## Driver app
Drivers use the same login page and sessions as everyone else (`POST /auth/register` with `role: "driver"`,
then `POST /auth/login`). Registering creates a pending login and a driver request linked to it; the station
manager approves it on Requests -> Drivers, which creates the driver (and vehicle, if given) and switches the
login on. A driver already in the system who has no login registers with their phone number, and approval links
the login to their record. A driver may only call `GET /driver/me` (and `/auth/me`), and `POST /tracking/position`
for their own vehicle (the driver Map tab). `GET /driver/me` includes each vehicle's map details: position,
destination, distance, direction and ETA. The driver app's "Directions with live traffic" button opens Google Maps. Demo driver: `0240000001` /
`driver123`. Existing databases: run `driver_accounts_migration.sql`.

## Mate (conductor) app
Mates tap "Mate" on the first screen, register or log in like staff (manager approval), and get their own app
with only the seat booking screen. On the backend a mate may only `GET /vehicles` and
`POST /vehicles/{id}/book-seats` / `release-seats`; everything else returns 403. Demo mate: `0200000004` / `mate123`.
Existing databases: run `mate_accounts_migration.sql`.

## Driver registration: how it works
1. The driver opens the dashboard's public page `/driver-register` (no sign-in) and sends their name, phone
   number and, optionally, their vehicle. The request is saved in `driver_requests` with status `pending`.
2. The station manager sees it on the dashboard's **Requests** tab (with a count on the tab) and approves or rejects it.
3. Approving creates the driver in `drivers` and, if a vehicle was given, the vehicle in `vehicles` (its route is
   found or created from the destination). Rejecting stores the reason.
4. The driver checks the result on the same page using their phone number.

Rules: one waiting request per phone number; a phone number or registration number that is already registered is
refused; a request can be reviewed only once. Every step is written to `audit_log`.

## Known limitations
- The public driver request endpoint has no rate limit or CAPTCHA, so someone could send many fake requests.
- Sending a position needs a staff sign-in. There is no separate driver login yet, so positions come from a
  staff member's device (the dashboard's Map page can send the device's GPS location) or are placed by hand.
- Position history is never deleted. Add a clean-up job if the table grows large.
- The database has no fare column, so fares are not returned.
- Only arrival time is stored; there is no estimated arrival time.
- The login attempt limiter is kept in memory (resets when the server restarts).
