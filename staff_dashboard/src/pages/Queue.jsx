import { useEffect, useState } from "react";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";

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
  }, []);

  async function run(action) {
    try {
      await action();
      setError("");
      await load();
    } catch (err) {
      setError(err.message);
    }
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

  const inQueue = queue.map((q) => q.vehicle.id);
  const notQueued = vehicles.filter((v) => !inQueue.includes(v.id));

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
              <option value="">{notQueued.length ? "Select vehicle" : "No vehicles available"}</option>
              {notQueued.map((v) => <option key={v.id} value={v.id}>{v.plate_number}</option>)}
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
              <tr><th>#</th><th>Plate</th><th>Arrived</th><th>Seats available</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {queue.map((q, i) => (
                <tr key={q.vehicle.id}>
                  <td>{q.position}</td>
                  <td>{q.vehicle.plate_number}</td>
                  <td>{new Date(q.arrived_at).toLocaleTimeString()}</td>
                  <td>{q.vehicle.seats_available} of {q.vehicle.seats_total}</td>
                  <td style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button className="secondary" onClick={() => move(i, -1)} disabled={i === 0}>
                      Move up
                    </button>
                    <button className="secondary" onClick={() => move(i, 1)} disabled={i === queue.length - 1}>
                      Move down
                    </button>
                    <button onClick={() => run(() => api.recordDeparture(q.vehicle.id))}>
                      Record departure
                    </button>
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
