import { useEffect, useState } from "react";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";

const REFRESH_SECONDS = 15; // other staff may change the queue, so it refreshes by itself

export default function Queue() {
  const [queue, setQueue] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const q = await api.getQueue();
      const v = await api.getVehicles();
      setQueue(q.queue);
      setVehicles(v.vehicles);
      setLastUpdated(q.last_updated);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_SECONDS * 1000);
    return () => clearInterval(timer);
  }, []);

  async function run(action) {
    try {
      await action();
      setError("");
    } catch (err) {
      setError(err.message);
    }
    await load(); // reload either way, so the screen always shows the real queue
  }

  function move(index, direction) {
    const ids = queue.map((q) => q.vehicle.id);
    const target = index + direction;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    run(() => api.saveQueueOrder(ids));
  }

  function handleArrival(e) {
    e.preventDefault();
    if (!selected) {
      setError("Please select a vehicle");
      return;
    }
    run(() => api.recordArrival(Number(selected)));
    setSelected("");
  }

  const canArrive = vehicles.filter((v) => !v.in_queue && v.status !== "unavailable");

  return (
    <>
      <h1>Vehicle queue</h1>
      {error && <p className="error" role="alert">{error}</p>}

      <div className="card">
        <h2>Record arrival</h2>
        <form className="row" onSubmit={handleArrival}>
          <label>
            Vehicle
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">
                {vehicles.length === 0 ? "No vehicles added yet" : canArrive.length ? "Select vehicle" : "All vehicles are in the queue"}
              </option>
              {canArrive.map((v) => <option key={v.id} value={v.id}>{v.plate_number}</option>)}
            </select>
          </label>
          <button type="submit">Record arrival</button>
        </form>
      </div>

      <div className="card">
        {queue.length === 0 ? (
          <p className="muted">No vehicles in the queue</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th><th>Registration</th><th>Arrived</th><th>Status</th><th>Seats available</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {queue.map((q, i) => {
                const loading = q.queue_status === "loading";
                return (
                  <tr key={q.vehicle.id}>
                    <td>{q.position}</td>
                    <td>{q.vehicle.plate_number}</td>
                    <td>{new Date(q.arrived_at).toLocaleTimeString()}</td>
                    <td><span className="chip">{loading ? "Loading" : "Waiting"}</span></td>
                    <td>
                      {q.vehicle.seats_available ?? "Unavailable"}
                      <span className="muted"> of {q.vehicle.seats_total}</span>
                    </td>
                    <td style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button className="secondary" onClick={() => move(i, -1)} disabled={i === 0}>Move up</button>
                      <button className="secondary" onClick={() => move(i, 1)} disabled={i === queue.length - 1}>Move down</button>
                      <button className="secondary"
                        onClick={() => run(() => api.updateVehicle(q.vehicle.id, { status: loading ? "queued" : "loading" }))}>
                        {loading ? "Back to waiting" : "Start loading"}
                      </button>
                      <button onClick={() => run(() => api.recordDeparture(q.vehicle.id))}>Record departure</button>
                      <button className="secondary" onClick={() => run(() => api.removeFromQueue(q.vehicle.id))}>Remove</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <LastUpdated value={lastUpdated} />
    </>
  );
}
