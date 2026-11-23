# Staff Dashboard (React)

Station staff interface for the Metro Trotro Information System: sign in, manage vehicles,
record arrivals, reorder the queue, record departures and view trips.

## Run it
Start the backend first (see `../backend/README.md`), then:
```
cd staff_dashboard
npm install
npm run dev
```
Open http://localhost:5173 and sign in with `demo@station.com` / `demo123` (manager)
or `ama@station.com` / `staff123` (staff, cannot add vehicles).

## Settings
All requests are in `src/api.js`.
- `VITE_API_URL` (default `http://localhost:8000`): address of the backend. Copy `.env.example` to `.env.local` to change it.
- `VITE_USE_MOCK=true` in `.env.local`: demo mode with fake in-memory data, no backend needed.

The backend's `CORS_ORIGINS` must include the address you open the dashboard on.

## Pages
- Queue: record arrival, move up/down, start loading, record departure, remove
- Vehicles: add a vehicle (managers), update seats and status
- Trips: search by destination and time period
