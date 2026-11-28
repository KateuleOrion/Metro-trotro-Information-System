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
//   route   : { id, name, from, to }          driver : { id, name, phone }
//   driver request : { id, name, phone, plate, destination, seats, status, reason,
//               submitted_at, reviewed_at, reviewed_by, driver_id, vehicle_id }
//               status = pending | approved | rejected
//   tracked vehicle : { id, plate_number, route_name, destination, destination_lat, destination_lon,
//               lat, lon, recorded_at, stale, age_minutes, distance_km, direction, eta_minutes, speed_kmh }
//               direction = approaching | moving_away | stopped | arrived | unknown | no_destination
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/* ====================================================================
   Demo mode: fake data in memory (lost when the page is refreshed)
   ==================================================================== */
const now = () => new Date().toISOString();
// Same rule as the backend: '+233 24 123 4567', '233241234567' and '024-123-4567' are one number.
export function normalizePhone(phone) {
  const text = phone.trim();
  const digits = text.replace(/\D/g, "");
  if (digits.startsWith("233") && digits.length === 12) return "0" + digits.slice(3);
  return text.startsWith("+") ? "+" + digits : digits;
}
const db = {
  staff: [
    { id: 1, name: "Demo Station Manager", phone: "0200000001", email: "demo@station.com", password: "demo123",
      role: "station_manager", status: "active", created_at: now() },
    { id: 2, name: "Ama Mensah", phone: "0200000002", email: "ama@station.com", password: "staff123",
      role: "station_staff", status: "active", created_at: now() },
    { id: 3, name: "Kwesi Owusu", phone: "0200000003", email: null, password: "staff456",
      role: "station_staff", status: "pending", created_at: now() },
    { id: 4, name: "Kofi Boateng", phone: "0200000004", email: null, password: "mate123",
      role: "mate", status: "active", created_at: now() },
  ],
  routes: [
    { id: 1, name: "Central - Madina", from: "Metro Central Station", to: "Madina" },
    { id: 2, name: "Central - Circle", from: "Metro Central Station", to: "Circle" },
    { id: 3, name: "Central - Kasoa", from: "Metro Central Station", to: "Kasoa" },
  ],
  drivers: [
    { id: 1, name: "Kwame Asare", phone: "0240000001" },
    { id: 2, name: "Kofi Mensah", phone: "0240000002" },
  ],
  driverRequests: [
    { id: 1, name: "Kojo Antwi", phone: "0245550101", plate: "GW-2201-25", destination: "Madina", seats: 14,
      status: "pending", reason: null, submitted_at: new Date(Date.now() - 3600e3).toISOString(),
      reviewed_at: null, reviewed_by: null, driver_id: null, vehicle_id: null },
    { id: 2, name: "Akosua Darko", phone: "0205550202", plate: null, destination: null, seats: null,
      status: "pending", reason: null, submitted_at: new Date(Date.now() - 1200e3).toISOString(),
      reviewed_at: null, reviewed_by: null, driver_id: null, vehicle_id: null },
  ],
  vehicles: [],
  // map demo data: where the destinations are (null = not set yet) and where each vehicle is
  station: { name: "Metro Central Station", lat: 5.5465, lon: -0.2063 },
  destinationCoords: { madina: [5.6693, -0.167], circle: [5.571, -0.218], kasoa: [5.534, -0.417] },
  positions: {}, // vehicle id -> { lat, lon, recorded_at }
  queue: [], // [{ vehicle_id, arrived_at, queue_status }]
  trips: [],
  last_updated: null,
  nextId: 100, // starts high: the sample routes (1-3) and drivers (1-2) already use the small ids
};
const touch = () => { db.last_updated = now(); };
const ok = (data) => new Promise((r) => setTimeout(() => r(structuredClone(data)), 150));
const fail = (msg) => new Promise((_, rej) => setTimeout(() => rej(new Error(msg)), 150));
const findVehicle = (id) => db.vehicles.find((v) => v.id === id);
const entryOf = (id) => db.queue.find((q) => q.vehicle_id === id);
const routeFor = (destination) => {
  // the existing route to this destination, or a new one
  const text = destination.trim();
  let route = db.routes.find((r) => r.to.toLowerCase() === text.toLowerCase());
  if (!route) {
    route = { id: db.nextId++, name: `${db.station.name} - ${text}`, from: db.station.name, to: text };
    db.routes.push(route);
  }
  return route.id;
};
function reviewStaff(id, changes) {
  const s = db.staff.find((x) => x.id === id);
  if (!s) return fail("Account not found");
  if (s.status !== "pending") return fail("This account is not waiting for approval");
  Object.assign(s, changes, { reviewed_at: now(), reviewed_by: "Demo Station Manager" });
  const { password: _password, ...rest } = s;
  return ok(rest);
}
const withRelations = (v) => ({
  ...v,
  route_name: db.routes.find((r) => r.id === v.route_id)?.name ?? null,
  driver_name: db.drivers.find((d) => d.id === v.driver_id)?.name ?? null,
  in_queue: !!entryOf(v.id),
});

function mockChangeSeats(id, delta) {
  const v = findVehicle(id);
  if (!v) return fail("Vehicle not found");
  if (v.status === "unavailable") return fail("This vehicle is marked unavailable");
  if (v.status === "departed") return fail("This vehicle has already departed");
  if (v.seats_available == null)
    return fail("Seats have not been set for this vehicle yet. Ask the station staff to set them");
  const left = v.seats_available;
  if (delta < 0 && left === 0) return fail("The vehicle is full. No seats left to book");
  if (delta < 0 && -delta > left)
    return fail(`Only ${left} seat${left !== 1 ? "s" : ""} left. Cannot book ${-delta} passengers`);
  if (delta > 0 && left + delta > v.seats_total) {
    const booked = v.seats_total - left;
    return fail(`Only ${booked} passenger${booked !== 1 ? "s are" : " is"} booked. Cannot cancel ${delta}`);
  }
  v.seats_available = left + delta;
  touch();
  return ok(withRelations(v));
}

const mock = {
  // login is a phone number, or an email for accounts registered with email
  login: (login, password) => {
    const key = login.includes("@") ? login.trim().toLowerCase() : normalizePhone(login);
    const s = db.staff.find((x) => (login.includes("@") ? x.email === key : x.phone === key));
    if (!s || s.password !== password) return fail("Wrong phone number, email or password");
    if (s.status === "pending") return fail("Your account is waiting for the station manager's approval");
    if (s.status === "rejected") return fail("Your registration was not approved. Please contact the station manager");
    return ok({ token: "fake-token", name: s.name, role: s.role, staff_id: s.id });
  },
  register: (r) => {
    const phone = r.phone ? normalizePhone(r.phone) : null;
    const email = r.email ? r.email.trim().toLowerCase() : null;
    if (phone && db.staff.some((x) => x.phone === phone))
      return fail("An account with this phone number already exists. Please log in instead");
    if (email && db.staff.some((x) => x.email === email))
      return fail("An account with this email already exists. Please log in instead");
    const s = { id: db.nextId++, name: r.name, phone, email, password: r.password, role: r.role,
      status: "pending", created_at: now() };
    db.staff.push(s);
    return ok({ account_status: "pending", staff_id: s.id });
  },
  getStaffAccounts: (status = "pending") => {
    const list = db.staff.filter((x) => x.status === status).map(({ password: _password, ...rest }) => rest);
    return ok(status === "pending" ? list : [...list].reverse());
  },
  approveStaffAccount: (id) => reviewStaff(id, { status: "active" }),
  rejectStaffAccount: (id, reason) => reviewStaff(id, { status: "rejected", reason: reason || null }),

  getRoutes: () => ok(db.routes),
  getDrivers: () => ok(db.drivers),
  getVehicles: () => ok({ vehicles: db.vehicles.map(withRelations), last_updated: db.last_updated }),

  addVehicle: (v) => {
    if (db.vehicles.some((x) => x.plate_number.toLowerCase() === v.plate_number.toLowerCase()))
      return fail("A vehicle with this registration number already exists");
    if (v.seats_available != null && v.seats_available > v.seats_total)
      return fail("Seats available cannot exceed the vehicle's capacity");
    // A typed-in destination is reused if it already exists, otherwise it is added.
    // The driver must already be registered (approved driver request).
    const route_id = v.route_id ?? routeFor(v.destination || "");
    const driver_id = v.driver_id ?? null;
    if (driver_id != null && !db.drivers.some((d) => d.id === driver_id)) return fail("Unknown route or driver");
    db.vehicles.push({
      id: db.nextId++,
      plate_number: v.plate_number.toUpperCase(),
      route_id,
      driver_id,
      seats_total: v.seats_total,
      seats_available: v.seats_available ?? v.seats_total,
      status: "available",
    });
    touch();
    return ok({ ok: true });
  },

  // mate / conductor page: book or cancel passengers on a vehicle
  bookSeats: (id, count) => mockChangeSeats(id, -count),
  releaseSeats: (id, count) => mockChangeSeats(id, count),

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

  // ---- map (demo): each vehicle starts at the station and drives toward its destination
  getTracking: () => {
    const toRad = (d) => (d * Math.PI) / 180;
    const km = (a, b) => {
      const h = Math.sin(toRad(b[0] - a[0]) / 2) ** 2 +
        Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(toRad(b[1] - a[1]) / 2) ** 2;
      return 2 * 6371 * Math.asin(Math.sqrt(h));
    };
    const vehicles = [];
    for (const v of db.vehicles) {
      const route = db.routes.find((r) => r.id === v.route_id);
      const dest = db.destinationCoords[(route?.to || "").toLowerCase()] || null;
      let pos = db.positions[v.id];
      if (!pos && dest) pos = db.positions[v.id] = { lat: db.station.lat, lon: db.station.lon, recorded_at: now() };
      if (!pos) continue;
      if (dest && pos.moving !== false) {
        // move 6% of the way to the destination on every refresh
        pos.lat += (dest[0] - pos.lat) * 0.06;
        pos.lon += (dest[1] - pos.lon) * 0.06;
        pos.recorded_at = now();
      }
      const dist = dest ? km([pos.lat, pos.lon], dest) : null;
      vehicles.push({
        id: v.id,
        plate_number: v.plate_number,
        route_name: route?.name ?? null,
        status: v.status,
        destination: route?.to ?? null,
        destination_lat: dest ? dest[0] : null,
        destination_lon: dest ? dest[1] : null,
        lat: pos.lat,
        lon: pos.lon,
        recorded_at: pos.recorded_at,
        stale: false,
        age_minutes: 0,
        distance_km: dist == null ? null : Math.round(dist * 100) / 100,
        direction: dist == null ? "no_destination" : dist <= 0.2 ? "arrived" : "approaching",
        eta_minutes: dist == null ? null : dist <= 0.2 ? 0 : Math.max(1, Math.round((dist / 30) * 60)),
        speed_kmh: 30,
      });
    }
    return ok({ vehicles, station: { ...db.station }, server_time: now() });
  },
  getDestinations: () =>
    ok(
      [...new Set(db.routes.map((r) => r.to))].map((name, i) => {
        const c = db.destinationCoords[name.toLowerCase()];
        return { id: i + 1, name, lat: c ? c[0] : null, lon: c ? c[1] : null };
      })
    ),
  reportPosition: (vehicle_id, lat, lon) => {
    if (!findVehicle(vehicle_id)) return fail("Vehicle not found");
    db.positions[vehicle_id] = { lat, lon, recorded_at: now(), moving: false }; // placed by hand: stays there
    return ok({ ok: true });
  },
  setDestinationLocation: (id, lat, lon) => {
    const names = [...new Set(db.routes.map((r) => r.to))];
    const name = names[id - 1];
    if (!name) return fail("Destination not found");
    db.destinationCoords[name.toLowerCase()] = [lat, lon];
    return ok({ ok: true });
  },

  // ---- driver registration requests (demo)
  submitDriverRequest: (r) => {
    if (db.drivers.some((d) => d.phone === r.phone)) return fail("A driver with this phone number is already registered");
    if (db.driverRequests.some((x) => x.phone === r.phone && x.status === "pending"))
      return fail("You already have a request waiting for the station manager");
    const plate = r.plate ? r.plate.toUpperCase() : null;
    if (plate && db.vehicles.some((v) => v.plate_number === plate))
      return fail("A vehicle with this registration number is already registered");
    const req = {
      id: db.nextId++, name: r.name, phone: r.phone, plate, destination: r.destination ?? null, seats: r.seats ?? null,
      status: "pending", reason: null, submitted_at: now(), reviewed_at: null, reviewed_by: null,
      driver_id: null, vehicle_id: null,
    };
    db.driverRequests.push(req);
    return ok({ id: req.id, status: req.status });
  },
  getDriverRequestStatus: (phone) => {
    const mine = db.driverRequests.filter((x) => x.phone === phone);
    if (!mine.length) return fail("No request found for this phone number");
    const r = mine[mine.length - 1];
    return ok({ id: r.id, status: r.status, reason: r.reason, submitted_at: r.submitted_at, reviewed_at: r.reviewed_at });
  },
  getDriverRequests: (status = "pending") => {
    const list = db.driverRequests.filter((x) => status === "all" || x.status === status);
    return ok(status === "pending" ? list : [...list].reverse());
  },
  approveDriverRequest: (id) => {
    const r = db.driverRequests.find((x) => x.id === id);
    if (!r) return fail("Request not found");
    if (r.status !== "pending") return fail(`This request has already been ${r.status}`);
    if (db.drivers.some((d) => d.phone === r.phone))
      return fail("A driver with this phone number is already registered. Reject this request instead");
    if (r.plate && db.vehicles.some((v) => v.plate_number === r.plate))
      return fail("A vehicle with this registration number is already registered. Reject this request instead");
    const driver = { id: db.nextId++, name: r.name, phone: r.phone };
    db.drivers.push(driver);
    if (r.plate) {
      const vehicle = {
        id: db.nextId++, plate_number: r.plate, route_id: routeFor(r.destination), driver_id: driver.id,
        seats_total: r.seats, seats_available: r.seats, status: "available",
      };
      db.vehicles.push(vehicle);
      r.vehicle_id = vehicle.id;
    }
    Object.assign(r, { status: "approved", driver_id: driver.id, reviewed_at: now(), reviewed_by: "Demo Station Manager" });
    touch();
    return ok(r);
  },
  rejectDriverRequest: (id, reason) => {
    const r = db.driverRequests.find((x) => x.id === id);
    if (!r) return fail("Request not found");
    if (r.status !== "pending") return fail(`This request has already been ${r.status}`);
    Object.assign(r, { status: "rejected", reason: reason || null, reviewed_at: now(), reviewed_by: "Demo Station Manager" });
    return ok(r);
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
    if (res.status === 401 && !path.startsWith("/auth/")) {
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

const toStaffAccount = (s) => ({
  id: s.staff_id,
  name: s.full_name,
  phone: s.phone_number,
  email: s.email,
  role: s.role,
  status: s.account_status,
  reason: s.reject_reason,
  created_at: s.created_at,
  reviewed_at: s.reviewed_at,
  reviewed_by: s.reviewed_by_name,
});

const toDriverRequest = (r) => ({
  id: r.request_id,
  name: r.full_name,
  phone: r.phone_number,
  plate: r.registration_number,
  destination: r.destination,
  seats: r.capacity,
  status: r.request_status,
  reason: r.reject_reason,
  submitted_at: r.submitted_at,
  reviewed_at: r.reviewed_at,
  reviewed_by: r.reviewed_by_name,
  driver_id: r.driver_id,
  vehicle_id: r.vehicle_id,
});

const real = {
  login: (login, password) => request("/auth/login", { method: "POST", body: json({ login, password }) }),
  register: async (r) => {
    const res = await request("/auth/register", {
      method: "POST",
      body: json({ full_name: r.name, role: r.role, phone_number: r.phone || null, email: r.email || null, password: r.password }),
    });
    return res; // { account_status: "pending" } or { account_status: "active", token, name, role, staff_id }
  },
  getStaffAccounts: async (status = "pending") =>
    (await request(`/staff/accounts?status=${status}`)).map(toStaffAccount),
  approveStaffAccount: async (id) => toStaffAccount(await request(`/staff/accounts/${id}/approve`, { method: "POST" })),
  rejectStaffAccount: async (id, reason) =>
    toStaffAccount(await request(`/staff/accounts/${id}/reject`, { method: "POST", body: json({ reason: reason || null }) })),

  getRoutes: async () =>
    (await request("/routes")).map((r) => ({ id: r.route_id, name: r.route_name, from: r.origin, to: r.destination })),
  getDrivers: async () =>
    (await request("/drivers")).map((d) => ({ id: d.driver_id, name: d.driver_name, phone: d.phone_number })),

  getVehicles: async () => {
    const r = await request("/vehicles");
    return { vehicles: r.vehicles.map(toVehicle), last_updated: r.last_updated };
  },
  addVehicle: (v) =>
    request("/vehicles", {
      method: "POST",
      body: json({
        registration_number: v.plate_number,
        // existing route by id, or a typed-in destination that the backend finds or adds;
        // the driver must be a registered one (by id)
        route_id: v.route_id ?? null,
        destination: v.destination ?? null,
        capacity: v.seats_total,
        driver_id: v.driver_id ?? null,
        available_seats: v.seats_available ?? null,
      }),
    }),
  bookSeats: async (id, count) =>
    toVehicle(await request(`/vehicles/${id}/book-seats`, { method: "POST", body: json({ count }) })),
  releaseSeats: async (id, count) =>
    toVehicle(await request(`/vehicles/${id}/release-seats`, { method: "POST", body: json({ count }) })),

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

  getTracking: async () => {
    const r = await request("/tracking/vehicles");
    return {
      vehicles: r.vehicles.map((v) => ({
        id: v.vehicle_id,
        plate_number: v.registration_number,
        route_name: v.route_name,
        status: v.vehicle_status,
        destination: v.destination,
        destination_lat: v.destination_latitude,
        destination_lon: v.destination_longitude,
        lat: v.latitude,
        lon: v.longitude,
        recorded_at: v.recorded_at,
        stale: v.stale,
        age_minutes: v.age_minutes,
        distance_km: v.distance_km,
        direction: v.direction,
        eta_minutes: v.eta_minutes,
        speed_kmh: v.speed_kmh,
      })),
      station: r.station && { name: r.station.station_name, lat: r.station.latitude, lon: r.station.longitude },
      server_time: r.server_time,
    };
  },
  getDestinations: async () =>
    (await request("/tracking/destinations")).map((d) => ({
      id: d.destination_id, name: d.destination_name, lat: d.latitude, lon: d.longitude,
    })),
  reportPosition: (vehicle_id, lat, lon, speed_kmh = null) =>
    request("/tracking/position", {
      method: "POST",
      body: json({ vehicle_id, latitude: lat, longitude: lon, speed_kmh }),
    }),
  setDestinationLocation: (id, lat, lon) =>
    request(`/tracking/destinations/${id}/location`, { method: "PUT", body: json({ latitude: lat, longitude: lon }) }),

  // ---- driver registration requests
  submitDriverRequest: async (r) => {
    const res = await request("/driver/requests", {
      method: "POST",
      body: json({
        full_name: r.name,
        phone_number: r.phone,
        registration_number: r.plate ?? null,
        destination: r.destination ?? null,
        capacity: r.seats ?? null,
      }),
    });
    return { id: res.request_id, status: res.request_status };
  },
  getDriverRequestStatus: async (phone) => {
    const r = await request(`/driver/requests/status?phone=${encodeURIComponent(phone)}`);
    return { id: r.request_id, status: r.request_status, reason: r.reject_reason, submitted_at: r.submitted_at, reviewed_at: r.reviewed_at };
  },
  getDriverRequests: async (status = "pending") =>
    (await request(`/driver/requests?status=${status}`)).map(toDriverRequest),
  approveDriverRequest: async (id) => toDriverRequest(await request(`/driver/requests/${id}/approve`, { method: "POST" })),
  rejectDriverRequest: async (id, reason) =>
    toDriverRequest(await request(`/driver/requests/${id}/reject`, { method: "POST", body: json({ reason: reason || null }) })),

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
