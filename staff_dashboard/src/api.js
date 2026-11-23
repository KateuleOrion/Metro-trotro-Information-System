// All communication with the backend is in this file.
//
//   Normal use : talks to the FastAPI backend. Its address comes from VITE_API_URL
//                (default http://localhost:8000).
//   Demo mode  : works with no backend, using fake data kept in the browser's memory.
//                Turn it on by creating a file called ".env.local" in this folder containing:
//                    VITE_USE_MOCK=true
//
// The pages use the same data shapes in both modes:
//   vehicle : { id, plate_number, route_id, route_name, driver_id, driver_name,
//               seats_total, seats_available (null = unknown), status, in_queue }
//   route   : { id, name, from, to }          driver : { id, name }
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/* ====================================================================
   Demo mode: fake data in memory (lost when the page is refreshed)
   ==================================================================== */
const now = () => new Date().toISOString();
const db = {
  routes: [
    { id: 1, name: "Central - Madina", from: "Metro Central Station", to: "Madina" },
    { id: 2, name: "Central - Circle", from: "Metro Central Station", to: "Circle" },
    { id: 3, name: "Central - Kasoa", from: "Metro Central Station", to: "Kasoa" },
  ],
  drivers: [
    { id: 1, name: "Kwame Asare" },
    { id: 2, name: "Kofi Mensah" },
  ],
  vehicles: [],
  queue: [], // [{ vehicle_id, arrived_at, queue_status }]
  trips: [],
  last_updated: null,
  nextId: 1,
};
const touch = () => { db.last_updated = now(); };
const ok = (data) => new Promise((r) => setTimeout(() => r(structuredClone(data)), 150));
const fail = (msg) => new Promise((_, rej) => setTimeout(() => rej(new Error(msg)), 150));
const findVehicle = (id) => db.vehicles.find((v) => v.id === id);
const entryOf = (id) => db.queue.find((q) => q.vehicle_id === id);
const withRelations = (v) => ({
  ...v,
  route_name: db.routes.find((r) => r.id === v.route_id)?.name ?? null,
  driver_name: db.drivers.find((d) => d.id === v.driver_id)?.name ?? null,
  in_queue: !!entryOf(v.id),
});

const mock = {
  login: (email, password) =>
    email.trim().toLowerCase() === "demo@station.com" && password === "demo123"
      ? ok({ token: "fake-token", name: "Demo Station Manager", role: "station_manager" })
      : fail("Wrong email or password"),

  getRoutes: () => ok(db.routes),
  getDrivers: () => ok(db.drivers),
  getVehicles: () => ok({ vehicles: db.vehicles.map(withRelations), last_updated: db.last_updated }),

  addVehicle: (v) => {
    if (db.vehicles.some((x) => x.plate_number.toLowerCase() === v.plate_number.toLowerCase()))
      return fail("A vehicle with this registration number already exists");
    if (v.seats_available != null && v.seats_available > v.seats_total)
      return fail("Seats available cannot exceed the vehicle's capacity");
    db.vehicles.push({
      id: db.nextId++,
      plate_number: v.plate_number.toUpperCase(),
      route_id: v.route_id,
      driver_id: v.driver_id ?? null,
      seats_total: v.seats_total,
      seats_available: v.seats_available ?? v.seats_total,
      status: "available",
    });
    touch();
    return ok({ ok: true });
  },

  updateVehicle: (id, c) => {
    const v = findVehicle(id);
    if (!v) return fail("Vehicle not found");
    const entry = entryOf(id);
    if (c.seats_available != null && c.seats_available > v.seats_total)
      return fail(`Seats available cannot exceed the vehicle's capacity (${v.seats_total})`);
    if (c.status && c.status !== v.status) {
      if (c.status === "departed") return fail("Use 'Record departure' in the queue to mark a vehicle as departed");
      if ((c.status === "queued" || c.status === "loading") && !entry)
        return fail("The vehicle is not in the queue. Record its arrival first");
      if (c.status === "available" && entry)
        return fail("The vehicle is in the queue. Remove it from the queue first");
      if (c.status === "queued") entry.queue_status = "waiting";
      if (c.status === "loading") entry.queue_status = "loading";
      if (c.status === "unavailable" && entry) db.queue = db.queue.filter((q) => q.vehicle_id !== id);
      v.status = c.status;
    }
    if (c.seats_available != null) v.seats_available = c.seats_available;
    touch();
    return ok({ ok: true });
  },

  getQueue: () =>
    ok({
      queue: db.queue.map((q, i) => ({
        position: i + 1,
        arrived_at: q.arrived_at,
        queue_status: q.queue_status,
        vehicle: { ...findVehicle(q.vehicle_id) },
      })),
      last_updated: db.last_updated,
    }),

  recordArrival: (vehicle_id) => {
    const v = findVehicle(vehicle_id);
    if (!v) return fail("Vehicle not found");
    if (v.status === "unavailable") return fail("This vehicle is marked unavailable. Set it to available first");
    if (entryOf(vehicle_id)) return fail("Vehicle is already in the queue");
    db.queue.push({ vehicle_id, arrived_at: now(), queue_status: "waiting" });
    v.status = "queued";
    touch();
    return ok({ ok: true });
  },

  saveQueueOrder: (ids) => {
    if (ids.length !== db.queue.length) return fail("The queue has changed. Refresh the page and try again");
    db.queue = ids.map((id) => entryOf(id));
    touch();
    return ok({ ok: true });
  },

  recordDeparture: (vehicle_id) => {
    if (!entryOf(vehicle_id)) return fail("Vehicle is not in the queue");
    const v = findVehicle(vehicle_id);
    db.queue = db.queue.filter((q) => q.vehicle_id !== vehicle_id);
    db.trips.push({
      id: db.nextId++,
      destination: db.routes.find((r) => r.id === v.route_id)?.name ?? null,
      departed_at: now(),
      plate_number: v.plate_number,
      driver: db.drivers.find((d) => d.id === v.driver_id)?.name ?? null,
      passengers: v.seats_available == null ? null : v.seats_total - v.seats_available,
      status: "Departed",
    });
    v.status = "departed";
    touch();
    return ok({ ok: true });
  },

  removeFromQueue: (vehicle_id) => {
    if (!entryOf(vehicle_id)) return fail("Vehicle is not in the queue");
    db.queue = db.queue.filter((q) => q.vehicle_id !== vehicle_id);
    findVehicle(vehicle_id).status = "available";
    touch();
    return ok({ ok: true });
  },

  getTrips: ({ destination = "", period = "all" } = {}) => {
    const text = destination.toLowerCase();
    const days = { today: 1, week: 7, month: 30 }[period];
    const since = days ? Date.now() - days * 86400000 : 0;
    return ok({
      trips: db.trips
        .filter((t) => !text || (t.destination || "").toLowerCase().includes(text))
        .filter((t) => new Date(t.departed_at).getTime() >= since)
        .reverse(),
      last_updated: db.last_updated,
    });
  },
};

/* ====================================================================
   Real backend (FastAPI)
   ==================================================================== */
async function request(path, options = {}) {
  const token = localStorage.getItem("token");
  let res;
  try {
    res = await fetch(BASE_URL + path, {
      ...options,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
  } catch {
    throw new Error(
      `Cannot reach the server at ${BASE_URL}. Check that the backend is running. ` +
        "If it is running, its CORS_ORIGINS setting must include this page's address."
    );
  }
  if (!res.ok) {
    if (res.status === 401 && path !== "/auth/login") {
      // The sign-in has expired: go back to the sign-in page.
      localStorage.removeItem("user");
      localStorage.removeItem("token");
      window.location.reload();
    }
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Something went wrong. Please try again.");
  }
  return res.json();
}
const json = (data) => JSON.stringify(data);

// Convert the backend's field names into the shapes the pages use.
const toVehicle = (v) => ({
  id: v.vehicle_id,
  plate_number: v.registration_number,
  route_id: v.route_id,
  route_name: v.route_name,
  driver_id: v.driver_id,
  driver_name: v.driver_name,
  seats_total: v.capacity,
  seats_available: v.available_seats,
  status: v.vehicle_status,
  in_queue: v.in_queue,
});

const real = {
  login: (email, password) => request("/auth/login", { method: "POST", body: json({ email, password }) }),

  getRoutes: async () =>
    (await request("/routes")).map((r) => ({ id: r.route_id, name: r.route_name, from: r.origin, to: r.destination })),
  getDrivers: async () => (await request("/drivers")).map((d) => ({ id: d.driver_id, name: d.driver_name })),

  getVehicles: async () => {
    const r = await request("/vehicles");
    return { vehicles: r.vehicles.map(toVehicle), last_updated: r.last_updated };
  },
  addVehicle: (v) =>
    request("/vehicles", {
      method: "POST",
      body: json({
        registration_number: v.plate_number,
        route_id: v.route_id,
        capacity: v.seats_total,
        driver_id: v.driver_id ?? null,
        available_seats: v.seats_available ?? null,
      }),
    }),
  updateVehicle: (id, c) => {
    const body = {};
    if ("status" in c) body.vehicle_status = c.status;
    if ("seats_available" in c) body.available_seats = c.seats_available;
    return request(`/vehicles/${id}`, { method: "PUT", body: json(body) });
  },

  getQueue: async () => {
    const r = await request("/queue");
    return {
      queue: r.queue.map((q) => ({
        position: q.position,
        arrived_at: q.arrival_time,
        queue_status: q.queue_status,
        vehicle: {
          id: q.vehicle.vehicle_id,
          plate_number: q.vehicle.registration_number,
          seats_total: q.vehicle.capacity,
          seats_available: q.vehicle.available_seats,
          status: q.vehicle.vehicle_status,
        },
      })),
      last_updated: r.last_updated,
    };
  },
  recordArrival: (vehicle_id) => request("/queue/arrivals", { method: "POST", body: json({ vehicle_id }) }),
  saveQueueOrder: (ids) => request("/queue/order", { method: "PUT", body: json({ vehicle_ids: ids }) }),
  recordDeparture: (vehicle_id) => request("/queue/departures", { method: "POST", body: json({ vehicle_id }) }),
  removeFromQueue: (vehicle_id) => request("/queue/cancel", { method: "POST", body: json({ vehicle_id }) }),

  getTrips: async ({ destination = "", period = "all" } = {}) => {
    const r = await request(`/trips?destination=${encodeURIComponent(destination)}&period=${period}`);
    return {
      trips: r.trips.map((t) => ({
        id: t.departure_id,
        destination: t.route_name,
        departed_at: t.departure_time,
        plate_number: t.registration_number,
        driver: t.driver_name,
        passengers: t.passengers,
        status: "Departed",
      })),
      last_updated: r.last_updated,
    };
  },
};

export const api = USE_MOCK ? mock : real;
export const isDemoMode = USE_MOCK;
