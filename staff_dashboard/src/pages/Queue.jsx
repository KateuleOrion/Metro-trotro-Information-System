import { useEffect, useState } from "react";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";

const REFRESH_SECONDS = 15; // other staff may change the queue, so it refreshes by itself

export default function Queue() {
  const [queue, setQueue] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [selected, setSelected] = useState("");
  const [open, setOpen] = useState(null); // vehicle id whose "More" actions are showing
  const [error, setError] = useState("");

  async function load() {
    try {
      const [q, v] = await Promise.all([api.getQueue(), api.getVehicles()]);
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
      {error && <p className="error" role="alert">{error}</p>}

      <div className="card">
        <form className="stack" onSubmit={handleArrival}>
          <label>
            A vehicle has arrived
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">
                {vehicles.length === 0 ? "No vehicles added yet" : canArrive.length ? "Select vehicle" : "All vehicles are in the queue"}
              </option>
              {canArrive.map((v) => <option key={v.id} value={v.id}>{v.plate_number}</option>)}
            </select>
          </label>
          <button type="submit" disabled={!canArrive.length}>Record arrival</button>
        </form>
      </div>

      {queue.length === 0 ? (
        <p className="empty">No vehicles in the queue</p>
      ) : (
        <div className="list">
          {queue.map((q, i) => {
            const loading = q.queue_status === "loading";
            const id = q.vehicle.id;
            return (
              <div className="item" key={id}>
                <div className="item-head">
                  <span className="pos" aria-label={`Position ${q.position}`}>{q.position}</span>
                  <span className="item-title">{q.vehicle.plate_number}</span>
                  <span className={`chip ${loading ? "loading" : ""}`}>{loading ? "Loading" : "Waiting"}</span>
                </div>
                <div className="item-sub">
                  Arrived {new Date(q.arrived_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  {" · "}
                  {q.vehicle.seats_available ?? "?"} of {q.vehicle.seats_total} seats free
                </div>

                <div className="actions">
                  <button className="full" onClick={() => run(() => api.recordDeparture(id))}>Record departure</button>
                  <button className="secondary"
                    onClick={() => run(() => api.updateVehicle(id, { status: loading ? "queued" : "loading" }))}>
                    {loading ? "Back to waiting" : "Start loading"}
                  </button>
                  <button className="secondary" aria-expanded={open === id} onClick={() => setOpen(open === id ? null : id)}>
                    {open === id ? "Less" : "More"}
                  </button>
                </div>

                {open === id && (
                  <div className="actions">
                    <button className="secondary" onClick={() => move(i, -1)} disabled={i === 0}>Move up</button>
                    <button className="secondary" onClick={() => move(i, 1)} disabled={i === queue.length - 1}>Move down</button>
                    <button className="danger full" onClick={() => run(() => api.removeFromQueue(id))}>Remove from queue</button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      <LastUpdated value={lastUpdated} />
    </>
  );
}
