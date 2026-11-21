# Staff Dashboard (React)

Station staff interface for the Metro Trotro Information System: sign in, manage vehicles,
record arrivals, reorder the queue, record departures and view trips.

## Run it
```
npm install
npm run dev
```
Open http://localhost:5173 and sign in with the demo account: `demo@station.com` / `demo123`.

## Mock data vs the real backend
All requests are in `src/api.js`.
- `USE_MOCK = true`: data is kept in memory (lost on refresh). No backend needed.
- `USE_MOCK = false`: calls the FastAPI backend at `http://localhost:8000`. The backend must
  enable CORS for `http://localhost:5173`. Endpoint and field names are defined in `src/api.js`.

## Pages
- Queue: record arrival, move up/down, record departure
- Vehicles: add a vehicle, update seats and status
- Trips: trips table with destination search
