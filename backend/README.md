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
Copy `.env.example` to `.env` and edit it (set your database password and a long random
`JWT_SECRET`). Never commit `.env`.

## 2. Run
```
uvicorn app.main:app --reload --port 8000
```
- Interactive API documentation: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Demo logins from the sample data: `demo@station.com` / `demo123` (manager),
  `ama@station.com` / `staff123` (staff). Plain-text sample passwords are replaced by bcrypt hashes
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
| POST /auth/login, GET /auth/me | anyone / staff | Sign in (JWT) |
| GET /routes, POST /routes | public / manager | Routes |
| GET /drivers, POST /drivers | staff / manager | Drivers |
| GET /vehicles, POST /vehicles, PUT /vehicles/{id} | staff / manager / staff | Vehicles, seats, status |
| GET /queue | public | Current queue |
| POST /queue/arrivals, PUT /queue/order, POST /queue/departures, POST /queue/cancel | staff | Manage the queue |
| GET /trips?destination=&period=all\|today\|week\|month | staff | Departure history |
| GET /passenger/search?from=&to= | public | Passenger vehicle search |
| GET /driver/vehicles, GET /driver/turn | public | Driver view |
| POST /sync/batch, POST /sync/upload, GET /sync/download | staff | Offline synchronisation |
| GET /activity | manager | Audit log |

Every queue change is written to `audit_log`, and queue changes at one station are serialised with a
database lock so two staff members cannot corrupt the order.

## Known limitations
- The database has no fare column, so fares are not returned.
- Only arrival time is stored; there is no estimated arrival time.
- The login attempt limiter is kept in memory (resets when the server restarts).
