import { useEffect, useState } from "react";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";
import { statusLabel } from "../labels";

const empty = { plate_number: "", driver_id: "", route_id: "", seats_total: "", seats_available: "" };
// 'Departed' is set by "Record departure" in the queue, so it is only shown when it is the current status.
const CHOOSABLE = ["available", "queued", "loading", "unavailable"];

function validate(f) {
  if (!f.plate_number.trim()) return "Please enter the registration number";
  if (!f.driver_id) return "Please select a driver";
  if (!f.route_id) return "Please select a route";
  if (f.seats_total === "") return "Please enter the total number of seats";
  const total = Number(f.seats_total);
  if (!Number.isInteger(total) || total < 1) return "Total seats must be a whole number of at least 1";
  if (f.seats_available !== "") {
    const avail = Number(f.seats_available);
    if (!Number.isInteger(avail) || avail < 0) return "Seats available must be a whole number, 0 or more";
    if (avail > total) return "Seats available cannot exceed total seats";
  }
  return "";
}

export default function Vehicles({ user }) {
  const [vehicles, setVehicles] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");
  const isManager = user?.role === "station_manager";

  async function load() {
    try {
      const v = await api.getVehicles();
      setVehicles(v.vehicles);
      setLastUpdated(v.last_updated);
      setRoutes(await api.getRoutes());
      setDrivers(await api.getDrivers());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function handleAdd(e) {
    e.preventDefault();
    const problem = validate(form);
    if (problem) {
      setError(problem);
      return;
    }
    try {
      await api.addVehicle({
        plate_number: form.plate_number.trim(),
        driver_id: Number(form.driver_id),
        route_id: Number(form.route_id),
        seats_total: Number(form.seats_total),
        seats_available: form.seats_available === "" ? null : Number(form.seats_available),
      });
      setForm(empty);
      setError("");
    } catch (err) {
      setError(err.message);
    }
    load();
  }

  async function change(id, changes) {
    try {
      await api.updateVehicle(id, changes);
      setError("");
    } catch (err) {
      setError(err.message);
    }
    load(); // reload either way, so a rejected change is shown as it really is
  }

  return (
    <>
      <h1>Vehicles</h1>
      {error && <p className="error" role="alert">{error}</p>}

      {isManager && (
        <div className="card">
          <h2>Add a vehicle</h2>
          <form className="row" onSubmit={handleAdd}>
            <label>
              Registration number
              <input value={form.plate_number} onChange={set("plate_number")} placeholder="e.g. GR-1234-24" />
            </label>
            <label>
              Driver
              <select value={form.driver_id} onChange={set("driver_id")}>
                <option value="">{drivers.length ? "Select driver" : "No drivers added yet"}</option>
                {drivers.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </label>
            <label>
              Route
              <select value={form.route_id} onChange={set("route_id")}>
                <option value="">{routes.length ? "Select route" : "No routes added yet"}</option>
                {routes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </label>
            <label>
              Total seats
              <input type="number" min="1" value={form.seats_total} onChange={set("seats_total")} />
            </label>
            <label>
              Seats available
              <input type="number" min="0" value={form.seats_available} onChange={set("seats_available")}
                placeholder="Same as total" />
            </label>
            <button type="submit">Add vehicle</button>
          </form>
        </div>
      )}

      <div className="card">
        {vehicles.length === 0 ? (
          <p className="muted">No vehicles added yet</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Registration</th><th>Driver</th><th>Route</th><th>Seats available</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.map((v) => (
                <tr key={v.id}>
                  <td>{v.plate_number}</td>
                  <td>{v.driver_name ?? "Unavailable"}</td>
                  <td>{v.route_name ?? "Unavailable"}</td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      max={v.seats_total}
                      style={{ width: 90 }}
                      placeholder="Unavailable"
                      aria-label={`Seats available for ${v.plate_number}`}
                      key={`${v.id}-${v.seats_available}`}
                      defaultValue={v.seats_available ?? ""}
                      onBlur={(e) => {
                        const text = e.target.value;
                        if (text !== "" && Number(text) !== v.seats_available)
                          change(v.id, { seats_available: Number(text) });
                      }}
                    />
                    <span className="muted"> of {v.seats_total}</span>
                  </td>
                  <td>
                    <select
                      value={v.status}
                      aria-label={`Status for ${v.plate_number}`}
                      onChange={(e) => change(v.id, { status: e.target.value })}
                    >
                      {(CHOOSABLE.includes(v.status) ? CHOOSABLE : [v.status, ...CHOOSABLE]).map((s) => (
                        <option key={s} value={s}>{statusLabel(s)}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <LastUpdated value={lastUpdated} />
    </>
  );
}
