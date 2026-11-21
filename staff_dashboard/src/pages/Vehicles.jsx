import { useEffect, useState } from "react";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";

const MAKES = ["Toyota", "Volvo", "Mercedes-Benz", "Other"];
const STATUSES = ["Not in queue", "Waiting in queue", "Loading", "In progress", "Completed"];
const empty = {
  plate_number: "", make: "", driver_id: "", route_id: "", seats_total: "", seats_available: "",
};

function validate(f) {
  if (!f.plate_number.trim()) return "Please enter the plate number";
  if (!f.make) return "Please select the vehicle make";
  if (!f.driver_id) return "Please select a driver";
  if (!f.route_id) return "Please select a route";
  if (f.seats_total === "" || f.seats_available === "")
    return "Please enter total seats and seats available";
  const total = Number(f.seats_total);
  const avail = Number(f.seats_available);
  if (!Number.isInteger(total) || total < 1) return "Total seats must be a whole number of at least 1";
  if (!Number.isInteger(avail) || avail < 0) return "Seats available must be a whole number, 0 or more";
  if (avail > total) return "Seats available cannot exceed total seats";
  return "";
}

export default function Vehicles() {
  const [vehicles, setVehicles] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [drivers, setDrivers] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");

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
        make: form.make,
        driver_id: Number(form.driver_id),
        route_id: Number(form.route_id),
        seats_total: Number(form.seats_total),
        seats_available: Number(form.seats_available),
        status: "Not in queue",
      });
      setForm(empty);
      setError("");
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function change(id, changes) {
    try {
      await api.updateVehicle(id, changes);
      setError("");
    } catch (err) {
      setError(err.message);
    }
    load();
  }

  const routeName = (id) => {
    const r = routes.find((x) => x.id === id);
    return r ? `${r.from} - ${r.to}` : "Unavailable";
  };
  const driverName = (id) => {
    const d = drivers.find((x) => x.id === id);
    return d ? d.name : "Unavailable";
  };

  return (
    <>
      <h1>Vehicles</h1>
      {error && <p className="error" role="alert">{error}</p>}

      <div className="card">
        <h2>Add a vehicle</h2>
        <form className="row" onSubmit={handleAdd}>
          <label>
            Plate number
            <input value={form.plate_number} onChange={set("plate_number")} placeholder="e.g. GR 1234-24" />
          </label>
          <label>
            Make
            <select value={form.make} onChange={set("make")}>
              <option value="">Select make</option>
              {MAKES.map((m) => <option key={m}>{m}</option>)}
            </select>
          </label>
          <label>
            Driver
            <select value={form.driver_id} onChange={set("driver_id")}>
              <option value="">Select driver</option>
              {drivers.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
          <label>
            Route
            <select value={form.route_id} onChange={set("route_id")}>
              <option value="">Select route</option>
              {routes.map((r) => <option key={r.id} value={r.id}>{r.from} - {r.to}</option>)}
            </select>
          </label>
          <label>
            Total seats
            <input type="number" min="1" value={form.seats_total} onChange={set("seats_total")} />
          </label>
          <label>
            Seats available
            <input type="number" min="0" value={form.seats_available} onChange={set("seats_available")} />
          </label>
          <button type="submit">Add vehicle</button>
        </form>
      </div>

      <div className="card">
        {vehicles.length === 0 ? (
          <p className="muted">No vehicles added yet</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Plate</th><th>Make</th><th>Driver</th><th>Route</th><th>Seats available</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.map((v) => (
                <tr key={v.id}>
                  <td>{v.plate_number}</td>
                  <td>{v.make}</td>
                  <td>{driverName(v.driver_id)}</td>
                  <td>{routeName(v.route_id)}</td>
                  <td>
                    <input
                      type="number"
                      min="0"
                      max={v.seats_total}
                      style={{ width: 80 }}
                      aria-label={`Seats available for ${v.plate_number}`}
                      key={`${v.id}-${v.seats_available}`}
                      defaultValue={v.seats_available}
                      onBlur={(e) =>
                        Number(e.target.value) !== v.seats_available &&
                        change(v.id, { seats_available: Number(e.target.value) })
                      }
                    />
                    <span className="muted"> of {v.seats_total}</span>
                  </td>
                  <td>
                    <select
                      value={v.status}
                      aria-label={`Status for ${v.plate_number}`}
                      onChange={(e) => change(v.id, { status: e.target.value })}
                    >
                      {STATUSES.map((s) => <option key={s}>{s}</option>)}
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
