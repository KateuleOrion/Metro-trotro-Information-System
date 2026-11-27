import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";
import { statusLabel } from "../labels";

const empty = { plate_number: "", driver_id: "", destination: "", seats_total: "", seats_available: "" };
// 'Departed' is set by "Record departure" in the queue, so it is only shown when it is the current status.
const CHOOSABLE = ["available", "queued", "loading", "unavailable"];

function validate(f) {
  if (!f.plate_number.trim()) return "Please enter the registration number";
  if (!f.destination.trim()) return "Please enter the destination";
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
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const isManager = user?.role === "station_manager";

  async function load() {
    try {
      const [v, r, d] = await Promise.all([api.getVehicles(), api.getRoutes(), api.getDrivers()]);
      setVehicles(v.vehicles);
      setLastUpdated(v.last_updated);
      setRoutes(r);
      setDrivers(d);
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
        driver_id: form.driver_id ? Number(form.driver_id) : null, // only registered (approved) drivers
        destination: form.destination.trim(), // the backend uses the existing route or adds a new one
        seats_total: Number(form.seats_total),
        seats_available: form.seats_available === "" ? null : Number(form.seats_available),
      });
      setNotice(`${form.plate_number.trim().toUpperCase()} added`);
      setForm(empty);
      setShowForm(false);
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
      {error && <p className="error" role="alert">{error}</p>}
      {notice && !error && <p className="notice" role="status">{notice}</p>}

      {isManager && !showForm && (
        <button style={{ marginBottom: 14 }} onClick={() => { setShowForm(true); setNotice(""); }}>
          + Add a vehicle
        </button>
      )}

      {isManager && showForm && (
        <div className="card">
          <h2>Add a vehicle</h2>
          <form className="stack" onSubmit={handleAdd}>
            <label>
              Registration number
              <input value={form.plate_number} onChange={set("plate_number")} placeholder="e.g. GR-1234-24"
                autoCapitalize="characters" />
            </label>
            <label>
              Driver
              <select value={form.driver_id} onChange={set("driver_id")}>
                <option value="">No driver yet</option>
                {drivers.map((d) => <option key={d.id} value={d.id}>{d.name}{d.phone ? ` (${d.phone})` : ""}</option>)}
              </select>
              <span className="hint">
                Only registered drivers are listed. New drivers send a request, which you approve
                under <Link to="/requests">Requests</Link>.
              </span>
            </label>
            <label>
              Destination
              <input list="destination-names" value={form.destination} onChange={set("destination")}
                placeholder="e.g. Madina" autoComplete="off" />
              <datalist id="destination-names">
                {[...new Set(routes.map((r) => r.to))].map((name) => <option key={name} value={name} />)}
              </datalist>
            </label>
            <div className="two">
              <label>
                Total seats
                <input type="number" inputMode="numeric" min="1" value={form.seats_total} onChange={set("seats_total")} />
              </label>
              <label>
                Seats free
                <input type="number" inputMode="numeric" min="0" value={form.seats_available}
                  onChange={set("seats_available")} placeholder="All" />
              </label>
            </div>
            <div className="actions">
              <button type="button" className="secondary" onClick={() => { setShowForm(false); setError(""); }}>Cancel</button>
              <button type="submit">Add vehicle</button>
            </div>
          </form>
        </div>
      )}

      {vehicles.length === 0 ? (
        <p className="empty">No vehicles added yet</p>
      ) : (
        <div className="list">
          {vehicles.map((v) => {
            const seats = v.seats_available;
            return (
              <div className="item" key={v.id}>
                <div className="item-head">
                  <span className="item-title">{v.plate_number}</span>
                  <span className={`chip ${v.status}`}>{statusLabel(v.status)}</span>
                </div>
                <dl className="facts">
                  <dt>Driver</dt><dd>{v.driver_name ?? "No driver"}</dd>
                  <dt>Route</dt><dd>{v.route_name ?? "Unavailable"}</dd>
                </dl>

                <div className="stack" style={{ marginTop: 12 }}>
                  <div>
                    <div className="hint" style={{ marginBottom: 5 }}>Seats free</div>
                    <div className="stepper">
                      <button className="secondary" aria-label={`One fewer seat free in ${v.plate_number}`}
                        disabled={seats == null || seats <= 0}
                        onClick={() => change(v.id, { seats_available: seats - 1 })}>−</button>
                      <span className="value">{seats ?? "?"} <small>of {v.seats_total}</small></span>
                      <button className="secondary" aria-label={`One more seat free in ${v.plate_number}`}
                        disabled={seats != null && seats >= v.seats_total}
                        onClick={() => change(v.id, { seats_available: seats == null ? v.seats_total : seats + 1 })}>+</button>
                    </div>
                  </div>
                  <label>
                    Status
                    <select
                      value={v.status}
                      aria-label={`Status for ${v.plate_number}`}
                      onChange={(e) => change(v.id, { status: e.target.value })}
                    >
                      {(CHOOSABLE.includes(v.status) ? CHOOSABLE : [v.status, ...CHOOSABLE]).map((s) => (
                        <option key={s} value={s}>{statusLabel(s)}</option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
            );
          })}
        </div>
      )}
      <LastUpdated value={lastUpdated} />
    </>
  );
}
