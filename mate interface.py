--- a/backend/app/schemas.py
+++ b/backend/app/schemas.py
@@ -32,6 +32,11 @@
     available_seats: Optional[int] = Field(default=None, ge=0)
 
 
+class SeatChange(Base):
+    """How many passengers a mate is booking onto, or taking off, a vehicle."""
+    count: int = Field(default=1, ge=1, le=100)
+
+
 class VehicleRef(Base):
     vehicle_id: int
 
--- a/backend/app/services.py
+++ b/backend/app/services.py
@@ -204,6 +204,36 @@
     )
 
 
+def change_seats(conn, staff_id: int, vehicle_id: int, delta: int) -> None:
+    """Book (delta < 0) or release (delta > 0) seats on a vehicle, with the checks done here.
+
+    The vehicle row is locked first, so if two mates book at the same moment the second one
+    sees the seats left by the first and cannot push the count below 0."""
+    v = get_vehicle(conn, vehicle_id, lock=True)
+    if v["vehicle_status"] == "unavailable":
+        raise ApiError(409, "This vehicle is marked unavailable")
+    if v["vehicle_status"] == "departed":
+        raise ApiError(409, "This vehicle has already departed")
+    row = conn.execute(
+        "SELECT available_seats FROM seat_availability WHERE vehicle_id = %s "
+        "ORDER BY last_updated DESC, seat_record_id DESC LIMIT 1",
+        (vehicle_id,),
+    ).fetchone()
+    if row is None:
+        raise ApiError(409, "Seats have not been set for this vehicle yet. Set them on the Vehicles page first")
+    left, capacity = row["available_seats"], v["capacity"]
+    if delta < 0 and left == 0:
+        raise ApiError(409, "The vehicle is full. No seats left to book")
+    if delta < 0 and -delta > left:
+        raise ApiError(409, f"Only {left} seat{'s' if left != 1 else ''} left. Cannot book {-delta} passengers")
+    if delta > 0 and left + delta > capacity:
+        booked = capacity - left
+        raise ApiError(409, f"Only {booked} passenger{'s are' if booked != 1 else ' is'} booked. Cannot cancel {delta}")
+    set_seats(conn, staff_id, vehicle_id, capacity, left + delta)
+    audit(conn, staff_id, "SEATS_BOOKED" if delta < 0 else "SEATS_RELEASED", "vehicles", vehicle_id,
+          {"count": abs(delta), "seats_before": left, "seats_after": left + delta})
+
+
 def update_vehicle(conn, staff_id: int, vehicle_id: int, changes: dict) -> None:
     v = get_vehicle(conn, vehicle_id, lock=True)
     entry = active_entry(conn, vehicle_id, lock=True)
--- a/backend/app/routers/vehicles.py
+++ b/backend/app/routers/vehicles.py
@@ -3,9 +3,9 @@
 
 from ..db import get_conn
 from ..errors import ApiError
-from ..schemas import VehicleCreate, VehicleUpdate
+from ..schemas import SeatChange, VehicleCreate, VehicleUpdate
 from ..security import current_staff, require_manager
-from ..services import audit, data_last_updated, set_seats, update_vehicle, vehicle_rows
+from ..services import audit, change_seats, data_last_updated, set_seats, update_vehicle, vehicle_rows
 
 router = APIRouter(prefix="/vehicles", tags=["Vehicles"])
 
@@ -46,3 +46,17 @@
     except pg.ForeignKeyViolation:
         raise ApiError(422, "Unknown route or driver")
     return vehicle_rows(conn, vehicle_id)[0]
+
+
+@router.post("/{vehicle_id}/book-seats")
+def book_seats(vehicle_id: int, body: SeatChange, staff=Depends(current_staff), conn=Depends(get_conn)):
+    """Mate books `count` passengers onto the vehicle. Refused if fewer seats are left."""
+    change_seats(conn, staff["staff_id"], vehicle_id, -body.count)
+    return vehicle_rows(conn, vehicle_id)[0]
+
+
+@router.post("/{vehicle_id}/release-seats")
+def release_seats(vehicle_id: int, body: SeatChange, staff=Depends(current_staff), conn=Depends(get_conn)):
+    """Mate cancels `count` bookings (a passenger got off or changed their mind)."""
+    change_seats(conn, staff["staff_id"], vehicle_id, body.count)
+    return vehicle_rows(conn, vehicle_id)[0]
--- a/staff_dashboard/src/api.js
+++ b/staff_dashboard/src/api.js
@@ -45,6 +45,26 @@
   in_queue: !!entryOf(v.id),
 });
 
+function mockChangeSeats(id, delta) {
+  const v = findVehicle(id);
+  if (!v) return fail("Vehicle not found");
+  if (v.status === "unavailable") return fail("This vehicle is marked unavailable");
+  if (v.status === "departed") return fail("This vehicle has already departed");
+  if (v.seats_available == null)
+    return fail("Seats have not been set for this vehicle yet. Set them on the Vehicles page first");
+  const left = v.seats_available;
+  if (delta < 0 && left === 0) return fail("The vehicle is full. No seats left to book");
+  if (delta < 0 && -delta > left)
+    return fail(`Only ${left} seat${left !== 1 ? "s" : ""} left. Cannot book ${-delta} passengers`);
+  if (delta > 0 && left + delta > v.seats_total) {
+    const booked = v.seats_total - left;
+    return fail(`Only ${booked} passenger${booked !== 1 ? "s are" : " is"} booked. Cannot cancel ${delta}`);
+  }
+  v.seats_available = left + delta;
+  touch();
+  return ok(withRelations(v));
+}
+
 const mock = {
   login: (email, password) =>
     email.trim().toLowerCase() === "demo@station.com" && password === "demo123"
@@ -95,6 +115,9 @@
     return ok({ ok: true });
   },
 
+  bookSeats: (id, count) => mockChangeSeats(id, -count),
+  releaseSeats: (id, count) => mockChangeSeats(id, count),
+
   getQueue: () =>
     ok({
       queue: db.queue.map((q, i) => ({
@@ -238,6 +261,11 @@
     return request(`/vehicles/${id}`, { method: "PUT", body: json(body) });
   },
 
+  bookSeats: async (id, count) =>
+    toVehicle(await request(`/vehicles/${id}/book-seats`, { method: "POST", body: json({ count }) })),
+  releaseSeats: async (id, count) =>
+    toVehicle(await request(`/vehicles/${id}/release-seats`, { method: "POST", body: json({ count }) })),
+
   getQueue: async () => {
     const r = await request("/queue");
     return {
--- a/staff_dashboard/src/App.jsx
+++ b/staff_dashboard/src/App.jsx
@@ -5,6 +5,7 @@
 import Queue from "./pages/Queue";
 import Vehicles from "./pages/Vehicles";
 import Trips from "./pages/Trips";
+import Mate from "./pages/Mate";
 
 export default function App() {
   const [user, setUser] = useState(() => JSON.parse(localStorage.getItem("user") || "null"));
@@ -31,6 +32,7 @@
           <Route path="/queue" element={<Queue />} />
           <Route path="/vehicles" element={<Vehicles user={user} />} />
           <Route path="/trips" element={<Trips />} />
+          <Route path="/mate" element={<Mate />} />
           <Route path="*" element={<Navigate to="/queue" />} />
         </Routes>
       </main>
--- a/staff_dashboard/src/components/NavBar.jsx
+++ b/staff_dashboard/src/components/NavBar.jsx
@@ -7,6 +7,7 @@
       <NavLink to="/queue">Queue</NavLink>
       <NavLink to="/vehicles">Vehicles</NavLink>
       <NavLink to="/trips">Trips</NavLink>
+      <NavLink to="/mate">Mate</NavLink>
       <span className="spacer" />
       <span className="muted">{user.name}</span>
       <button className="secondary" onClick={onLogout}>Sign out</button>
--- a/staff_dashboard/src/index.css
+++ b/staff_dashboard/src/index.css
@@ -155,4 +155,56 @@
     display: flex;
     flex-direction: column;
     gap: 14px;
-}
\ No newline at end of file
+}
+
+/* Mate / conductor page */
+.seat-board {
+    display: flex;
+    gap: 32px;
+    flex-wrap: wrap;
+    align-items: baseline;
+}
+
+.seat-number {
+    font-size: 64px;
+    font-weight: 700;
+    line-height: 1;
+}
+
+.meter {
+    height: 14px;
+    border-radius: 999px;
+    background: #E6ECE8;
+    overflow: hidden;
+    margin: 16px 0 8px;
+}
+
+.meter > div {
+    height: 100%;
+    background: var(--green);
+    transition: width 0.3s;
+}
+
+.chip.warn {
+    background: #FEF3C7;
+    color: #78350F;
+}
+
+.chip.full {
+    background: #FDECEC;
+    color: #9B1C1C;
+}
+
+.success {
+    color: #14532D;
+    background: #DDF3E6;
+    padding: 10px 14px;
+    border-radius: 10px;
+}
+
+.warning {
+    color: #78350F;
+    background: #FEF3C7;
+    padding: 10px 14px;
+    border-radius: 10px;
+}
--- a/staff_dashboard/src/pages/Mate.jsx
+++ b/staff_dashboard/src/pages/Mate.jsx
@@ -0,0 +1,204 @@
+import { useEffect, useState } from "react";
+import { api } from "../api";
+import LastUpdated from "../components/LastUpdated";
+import { statusLabel } from "../labels";
+
+const REFRESH_SECONDS = 15; // passengers may also book from the app, so the seat count refreshes by itself
+const LOW_SEATS = 2; // "Almost full" warning at or below this many seats
+
+const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
+
+// Why a booking (or cancellation) cannot go ahead, or "" if it is fine. The server checks again.
+function checkRequest(vehicle, text, mode) {
+  if (!vehicle) return "Select your vehicle first";
+  if (vehicle.status === "departed") return "This vehicle has already departed";
+  if (vehicle.status === "unavailable") return "This vehicle is marked unavailable";
+  if (vehicle.seats_available == null)
+    return "Seat count is not set for this vehicle. Set it on the Vehicles page first";
+  if (text === "") return "Enter the number of passengers";
+  const n = Number(text);
+  if (!Number.isInteger(n) || n < 1) return "Number of passengers must be a whole number of at least 1";
+  const left = vehicle.seats_available;
+  const booked = vehicle.seats_total - left;
+  if (mode === "book") {
+    if (left === 0) return "The vehicle is full. No seats left to book";
+    if (n > left) return `Only ${plural(left, "seat")} left. You cannot book ${plural(n, "passenger")}`;
+  } else {
+    if (booked === 0) return "No passengers are booked on this vehicle";
+    if (n > booked) return `Only ${plural(booked, "passenger")} ${booked === 1 ? "is" : "are"} booked. You cannot cancel ${n}`;
+  }
+  return "";
+}
+
+export default function Mate() {
+  const [vehicles, setVehicles] = useState([]);
+  const [vehicleId, setVehicleId] = useState(() => localStorage.getItem("mate_vehicle") || "");
+  const [count, setCount] = useState("1");
+  const [lastUpdated, setLastUpdated] = useState(null);
+  const [error, setError] = useState("");
+  const [message, setMessage] = useState("");
+  const [log, setLog] = useState([]); // this session's bookings, newest first
+  const [busy, setBusy] = useState(false);
+
+  async function load() {
+    try {
+      const v = await api.getVehicles();
+      setVehicles(v.vehicles);
+      setLastUpdated(v.last_updated);
+    } catch (err) {
+      setError(err.message);
+    }
+  }
+
+  useEffect(() => {
+    load();
+    const timer = setInterval(load, REFRESH_SECONDS * 1000);
+    return () => clearInterval(timer);
+  }, []);
+
+  function chooseVehicle(id) {
+    setVehicleId(id);
+    localStorage.setItem("mate_vehicle", id);
+    setError("");
+    setMessage("");
+  }
+
+  const vehicle = vehicles.find((v) => String(v.id) === String(vehicleId)) ?? null;
+  const total = vehicle?.seats_total ?? 0;
+  const left = vehicle?.seats_available ?? null;
+  const onBoard = left == null ? null : total - left;
+  const full = left === 0;
+  const almostFull = left != null && left > 0 && left <= LOW_SEATS;
+  const percentFull = left == null || total === 0 ? 0 : Math.round((onBoard / total) * 100);
+
+  const bookProblem = checkRequest(vehicle, count, "book");
+  const cancelProblem = checkRequest(vehicle, count, "cancel");
+  // Only show the typed-in problem as a live hint once the mate has chosen a vehicle.
+  const hint = vehicle && vehicle.seats_available != null ? bookProblem : "";
+
+  async function submit(mode) {
+    const problem = mode === "book" ? bookProblem : cancelProblem;
+    if (problem) {
+      setError(problem);
+      setMessage("");
+      return;
+    }
+    const n = Number(count);
+    setBusy(true);
+    try {
+      const updated =
+        mode === "book" ? await api.bookSeats(vehicle.id, n) : await api.releaseSeats(vehicle.id, n);
+      const text =
+        mode === "book"
+          ? `Booked ${plural(n, "passenger")}. ${plural(updated.seats_available, "seat")} left.`
+          : `Cancelled ${plural(n, "booking")}. ${plural(updated.seats_available, "seat")} left.`;
+      setMessage(text);
+      setError("");
+      setLog((l) => [{ time: new Date(), text }, ...l].slice(0, 8));
+      setCount("1");
+    } catch (err) {
+      setError(err.message);
+      setMessage("");
+    }
+    setBusy(false);
+    await load(); // reload either way, so the screen shows the real seat count
+  }
+
+  const choosable = vehicles.filter((v) => v.status !== "unavailable");
+
+  return (
+    <>
+      <h1>Mate / conductor</h1>
+      {error && <p className="error" role="alert">{error}</p>}
+      {message && <p className="success" role="status">{message}</p>}
+
+      <div className="card">
+        <form className="row" onSubmit={(e) => e.preventDefault()}>
+          <label>
+            Your vehicle
+            <select value={vehicleId} onChange={(e) => chooseVehicle(e.target.value)}>
+              <option value="">{choosable.length ? "Select vehicle" : "No vehicles added yet"}</option>
+              {choosable.map((v) => (
+                <option key={v.id} value={v.id}>
+                  {v.plate_number}{v.route_name ? ` - ${v.route_name}` : ""}
+                </option>
+              ))}
+            </select>
+          </label>
+        </form>
+      </div>
+
+      {vehicle && (
+        <>
+          <div className="card">
+            <div className="seat-board">
+              <div>
+                <div className="muted">Seats available</div>
+                <div className="seat-number">{left ?? "?"}</div>
+                <div className="muted">of {total}</div>
+              </div>
+              <div>
+                <div className="muted">Passengers booked</div>
+                <div className="seat-number">{onBoard ?? "?"}</div>
+                <div className="muted">on {vehicle.plate_number}</div>
+              </div>
+              <div>
+                {left == null ? (
+                  <span className="chip warn">Seat count unavailable</span>
+                ) : full ? (
+                  <span className="chip full">Full</span>
+                ) : almostFull ? (
+                  <span className="chip warn">Almost full</span>
+                ) : (
+                  <span className="chip">Seats available</span>
+                )}
+                <div className="muted" style={{ marginTop: 8 }}>
+                  Status: {statusLabel(vehicle.status)}
+                </div>
+              </div>
+            </div>
+            <div className="meter" role="progressbar" aria-valuemin={0} aria-valuemax={total}
+              aria-valuenow={onBoard ?? 0} aria-label="Seats taken">
+              <div style={{ width: `${percentFull}%` }} />
+            </div>
+            {full && <p className="warning">The vehicle is full. Go to the Queue page to record its departure.</p>}
+          </div>
+
+          <div className="card">
+            <h2>Book seats</h2>
+            <form className="row" onSubmit={(e) => { e.preventDefault(); submit("book"); }}>
+              <label>
+                Number of passengers
+                <input type="number" min="1" max={left ?? undefined} value={count}
+                  onChange={(e) => { setCount(e.target.value); setError(""); setMessage(""); }} />
+              </label>
+              <button type="submit" disabled={busy || !!bookProblem}>Book seats</button>
+              <button type="button" className="secondary" disabled={busy || !!cancelProblem}
+                onClick={() => submit("cancel")}>
+                Cancel booking
+              </button>
+            </form>
+            {hint && <p className="muted" style={{ marginBottom: 0 }}>{hint}</p>}
+          </div>
+
+          {log.length > 0 && (
+            <div className="card">
+              <h2>This session</h2>
+              <table>
+                <tbody>
+                  {log.map((entry, i) => (
+                    <tr key={i}>
+                      <td className="muted">{entry.time.toLocaleTimeString()}</td>
+                      <td>{entry.text}</td>
+                    </tr>
+                  ))}
+                </tbody>
+              </table>
+            </div>
+          )}
+        </>
+      )}
+      <LastUpdated value={lastUpdated} />
+    </>
+  );
+}