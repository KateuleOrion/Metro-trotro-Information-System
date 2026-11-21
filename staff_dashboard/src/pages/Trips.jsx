import { useEffect, useState } from "react";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";

export default function Trips() {
  const [trips, setTrips] = useState([]);
  const [destination, setDestination] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getTrips({ destination })
      .then((r) => {
        setTrips(r.trips);
        setLastUpdated(r.last_updated);
        setError("");
      })
      .catch((err) => setError(err.message));
  }, [destination]);

  return (
    <>
      <h1>Trips</h1>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="card">
        <input
          aria-label="Search by destination"
          placeholder="Search by destination"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
        />
      </div>
      <div className="card">
        {trips.length === 0 ? (
          <p className="muted">No trips recorded yet</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Destination</th><th>Date &amp; time</th><th>Vehicle</th>
                <th>Driver</th><th># Passengers</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {trips.map((t) => (
                <tr key={t.id}>
                  <td>{t.destination ?? "Unavailable"}</td>
                  <td>{new Date(t.departed_at).toLocaleString()}</td>
                  <td>{t.plate_number}</td>
                  <td>{t.driver ?? "Unavailable"}</td>
                  <td>{t.passengers ?? "Unavailable"}</td>
                  <td><span className="chip">{t.status}</span></td>
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
