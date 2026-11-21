// Set USE_MOCK to false when the FastAPI backend is ready.
const USE_MOCK = true;
const BASE_URL = "http://localhost:8000";

/* ---------- Mock data (kept in memory, lost on page refresh) ---------- */
const now = () => new Date().toISOString();
const db = {
  routes: [
    { id: 1, from: "Aburi", to: "Madina", fare: 12.5 },
    { id: 2, from: "Berekuso", to: "Kwabenya", fare: 8 },
  ],
  drivers: [
    { id: 1, name: "Driver One" },
    { id: 2, name: "Driver Two" },
  ],
  vehicles: [],
  queue: [], // [{ vehicle_id, arrived_at }]
  trips: [],
  last_updated: null,
  nextId: 1,
};
const touch = () => { db.last_updated = now(); };
const ok = (data) => new Promise((r) => setTimeout(() => r(structuredClone(data)), 150));
const fail = (msg) => new Promise((_, rej) => setTimeout(() => rej(new Error(msg)), 150));
const findVehicle = (id) => db.vehicles.find((v) => v.id === id);

const mock = {
  login: (email, password) =>
    email === "demo@station.com" && password === "demo123"
      ? ok({ token: "fake-token", name: "Demo Staff" })
      : fail("Wrong email or password"),

  getRoutes: () => ok(db.routes),
  getDrivers: () => ok(db.drivers),
  getVehicles: () => ok({ vehicles: db.vehicles, last_updated: db.last_updated }),

  addVehicle: (v) => {
    if (db.vehicles.some((x) => x.plate_number.toLowerCase() === v.plate_number.toLowerCase()))
      return fail("A vehicle with this plate number already exists");
    db.vehicles.push({ ...v, id: db.nextId++ });
    touch();
    return ok({ ok: true });
  },

  updateVehicle: (id, changes) => {
    const v = findVehicle(id);
    if (!v) return fail("Vehicle not found");
    const next = { ...v, ...changes };
    if (next.seats_available > next.seats_total)
      return fail("Seats available cannot exceed total seats");
    Object.assign(v, next);
    touch();
    return ok({ ok: true });
  },

  getQueue: () =>
    ok({
      queue: db.queue.map((q, i) => ({
        position: i + 1,
        arrived_at: q.arrived_at,
        vehicle: findVehicle(q.vehicle_id),
      })),
      last_updated: db.last_updated,
    }),

  recordArrival: (vehicle_id) => {
    if (db.queue.some((q) => q.vehicle_id === vehicle_id))
      return fail("Vehicle is already in the queue");
    db.queue.push({ vehicle_id, arrived_at: now() });
    findVehicle(vehicle_id).status = "Waiting in queue";
    touch();
    return ok({ ok: true });
  },

  saveQueueOrder: (ids) => {
    db.queue = ids.map((id) => db.queue.find((q) => q.vehicle_id === id));
    touch();
    return ok({ ok: true });
  },

  recordDeparture: (vehicle_id) => {
    if (!db.queue.some((q) => q.vehicle_id === vehicle_id))
      return fail("Vehicle is not in the queue");
    db.queue = db.queue.filter((q) => q.vehicle_id !== vehicle_id);
    const v = findVehicle(vehicle_id);
    const route = db.routes.find((r) => r.id === v.route_id);
    const driver = db.drivers.find((d) => d.id === v.driver_id);
    db.trips.push({
      id: db.nextId++,
      destination: route ? `${route.from} - ${route.to}` : null,
      departed_at: now(),
      plate_number: v.plate_number,
      driver: driver ? driver.name : null,
      passengers: v.seats_total - v.seats_available,
      status: "In progress",
    });
    v.status = "In progress";
    touch();
    return ok({ ok: true });
  },

  getTrips: ({ destination = "" } = {}) => {
    const q = destination.toLowerCase();
    return ok({
      trips: db.trips.filter((t) => !q || (t.destination || "").toLowerCase().includes(q)),
      last_updated: db.last_updated,
    });
  },
};

/* ---------- Real backend (FastAPI) ---------- */
async function request(path, options = {}) {
  const token = localStorage.getItem("token");
  const res = await fetch(BASE_URL + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Something went wrong. Please try again.");
  }
  return res.json();
}
const json = (data) => JSON.stringify(data);

const real = {
  login: (email, password) =>
    request("/auth/login", { method: "POST", body: json({ email, password }) }),
  getRoutes: () => request("/routes"),
  getDrivers: () => request("/drivers"),
  getVehicles: () => request("/vehicles"),
  addVehicle: (v) => request("/vehicles", { method: "POST", body: json(v) }),
  updateVehicle: (id, c) => request(`/vehicles/${id}`, { method: "PUT", body: json(c) }),
  getQueue: () => request("/queue"),
  recordArrival: (vehicle_id) =>
    request("/queue/arrivals", { method: "POST", body: json({ vehicle_id }) }),
  saveQueueOrder: (ids) =>
    request("/queue/order", { method: "PUT", body: json({ vehicle_ids: ids }) }),
  recordDeparture: (vehicle_id) =>
    request("/queue/departures", { method: "POST", body: json({ vehicle_id }) }),
  getTrips: (f = {}) => request(`/trips?destination=${encodeURIComponent(f.destination || "")}`),
};

export const api = USE_MOCK ? mock : real;
