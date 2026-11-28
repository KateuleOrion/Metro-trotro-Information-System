import { useEffect, useState } from "react";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";
import { statusLabel } from "../labels";

// The driver's own app: their vehicles, their place in the queue and seats free.
// It reads from the same database as the staff and mate apps and refreshes by itself.
const REFRESH_SECONDS = 15;

function queueText(v) {
  if (v.status === "departed") return "Departed";
  if (!v.in_queue) return "Not in the queue";
  if (v.is_my_turn) return v.queue_status === "loading" ? "Your turn. Loading now" : "Your turn to load";
  return `Number ${v.queue_position} in the queue`;
}

export default function DriverHome() {
  const [me, setMe] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      setMe(await api.getDriverMe());
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_SECONDS * 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <>
      {error && <p className="error" role="alert">{error}</p>}

      {me && me.vehicles.length === 0 && (
        <p className="empty">No vehicle is linked to you yet. Please ask the station manager.</p>
      )}

      {me?.vehicles.map((v) => (
        <div className="card" key={v.id}>
          {v.is_my_turn && <p className="notice turn" role="status">{queueText(v)}</p>}
          <div className="item-head">
            <span className="item-title">{v.plate_number}</span>
            <span className={`chip ${v.is_my_turn ? "" : v.in_queue ? "pending" : "grey"}`}>
              {v.in_queue ? (v.is_my_turn ? "Your turn" : `No. ${v.queue_position}`) : statusLabel(v.status)}
            </span>
          </div>
          <div className="item-sub">{v.route_name ?? "Route unavailable"}</div>

          <div className="seat-board">
            <div>
              <div className="seat-number">{v.in_queue ? v.vehicles_ahead : "-"}</div>
              <div className="muted">{v.in_queue ? `${v.vehicles_ahead === 1 ? "vehicle" : "vehicles"} ahead` : "not queued"}</div>
            </div>
            <div>
              <div className="seat-number">{v.seats_available ?? "?"}</div>
              <div className="muted">seats free of {v.seats_total}</div>
            </div>
          </div>

          <dl className="facts">
            <dt>Queue</dt><dd>{queueText(v)}</dd>
            <dt>Passengers</dt><dd>{v.seats_available == null ? "Unknown" : `${v.seats_total - v.seats_available} booked`}</dd>
          </dl>
        </div>
      ))}

      <button className="secondary" onClick={load}>Refresh</button>
      <LastUpdated value={me?.last_updated} />
    </>
  );
}
