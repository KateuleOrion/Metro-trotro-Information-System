import { useEffect, useState } from "react";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";
import { PERIODS } from "../labels";

export default function Trips() {
  const [trips, setTrips] = useState([]);
  const [destination, setDestination] = useState("");
  const [period, setPeriod] = useState("all");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getTrips({ destination, period })
      .then((r) => {
        setTrips(r.trips);
        setLastUpdated(r.last_updated);
        setError("");
      })
      .catch((err) => setError(err.message));
  }, [destination, period]);

  return (
    <>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="card">
        <form className="stack" onSubmit={(e) => e.preventDefault()}>
          <input
            type="search"
            aria-label="Search by destination"
            placeholder="Search by destination"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          />
          <select aria-label="Time period" value={period} onChange={(e) => setPeriod(e.target.value)}>
            {PERIODS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </form>
      </div>

      {trips.length === 0 ? (
        <p className="empty">No trips found</p>
      ) : (
        <div className="list">
          {trips.map((t) => (
            <div className="item" key={t.id}>
              <div className="item-head">
                <span className="item-title">{t.destination ?? "Unavailable"}</span>
                <span className="chip grey">{t.status}</span>
              </div>
              <div className="item-sub">{new Date(t.departed_at).toLocaleString()}</div>
              <dl className="facts">
                <dt>Vehicle</dt><dd>{t.plate_number}</dd>
                <dt>Driver</dt><dd>{t.driver ?? "Unavailable"}</dd>
                <dt>Passengers</dt><dd>{t.passengers ?? "Unavailable"}</dd>
              </dl>
            </div>
          ))}
        </div>
      )}
      <LastUpdated value={lastUpdated} />
    </>
  );
}
