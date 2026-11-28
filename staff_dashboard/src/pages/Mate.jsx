import { useEffect, useState } from "react";
import { api } from "../api";
import LastUpdated from "../components/LastUpdated";
import { statusLabel } from "../labels";

// Mate / conductor page: choose your vehicle, then book passengers on or cancel bookings.
const REFRESH_SECONDS = 15; // passengers may also book from the app, so the seat count refreshes by itself
const LOW_SEATS = 2; // "Almost full" warning at or below this many seats

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// Why a booking (or cancellation) cannot go ahead, or "" if it is fine. The server checks again.
function checkRequest(vehicle, n, mode) {
  if (!vehicle) return "Select your vehicle first";
  if (vehicle.status === "departed") return "This vehicle has already departed";
  if (vehicle.status === "unavailable") return "This vehicle is marked unavailable";
  if (vehicle.seats_available == null) return "Seat count is not set for this vehicle. Ask the station staff to set it";
  if (!Number.isInteger(n) || n < 1) return "Number of passengers must be at least 1";
  const left = vehicle.seats_available;
  const booked = vehicle.seats_total - left;
  if (mode === "book") {
    if (left === 0) return "The vehicle is full. No seats left to book";
    if (n > left) return `Only ${plural(left, "seat")} left. You cannot book ${plural(n, "passenger")}`;
  } else {
    if (booked === 0) return "No passengers are booked on this vehicle";
    if (n > booked) return `Only ${plural(booked, "passenger")} ${booked === 1 ? "is" : "are"} booked. You cannot cancel ${n}`;
  }
  return "";
}

export default function Mate() {
  const [vehicles, setVehicles] = useState([]);
  const [vehicleId, setVehicleId] = useState(() => localStorage.getItem("mate_vehicle") || "");
  const [count, setCount] = useState(1);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [log, setLog] = useState([]); // this session's bookings, newest first
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const v = await api.getVehicles();
      setVehicles(v.vehicles);
      setLastUpdated(v.last_updated);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, REFRESH_SECONDS * 1000);
    return () => clearInterval(timer);
  }, []);

  function chooseVehicle(id) {
    setVehicleId(id);
    localStorage.setItem("mate_vehicle", id);
    setError("");
    setMessage("");
    setCount(1);
  }

  const vehicle = vehicles.find((v) => String(v.id) === String(vehicleId)) ?? null;
  const total = vehicle?.seats_total ?? 0;
  const left = vehicle?.seats_available ?? null;
  const onBoard = left == null ? null : total - left;
  const full = left === 0;
  const almostFull = left != null && left > 0 && left <= LOW_SEATS;
  const percentFull = left == null || total === 0 ? 0 : Math.round((onBoard / total) * 100);

  const bookProblem = checkRequest(vehicle, count, "book");
  const cancelProblem = checkRequest(vehicle, count, "cancel");

  async function submit(mode) {
    const problem = mode === "book" ? bookProblem : cancelProblem;
    if (problem) {
      setError(problem);
      setMessage("");
      return;
    }
    setBusy(true);
    try {
      const updated = mode === "book" ? await api.bookSeats(vehicle.id, count) : await api.releaseSeats(vehicle.id, count);
      const text =
        mode === "book"
          ? `Booked ${plural(count, "passenger")}. ${plural(updated.seats_available, "seat")} left.`
          : `Cancelled ${plural(count, "booking")}. ${plural(updated.seats_available, "seat")} left.`;
      setMessage(text);
      setError("");
      setLog((l) => [{ time: new Date(), text }, ...l].slice(0, 8));
      setCount(1);
    } catch (err) {
      setError(err.message);
      setMessage("");
    }
    setBusy(false);
    await load(); // reload either way, so the screen shows the real seat count
  }

  const choosable = vehicles.filter((v) => v.status !== "unavailable");

  return (
    <>
      {error && <p className="error" role="alert">{error}</p>}
      {message && !error && <p className="notice" role="status">{message}</p>}

      <div className="card">
        <label>
          Your vehicle
          <select value={vehicleId} onChange={(e) => chooseVehicle(e.target.value)}>
            <option value="">{choosable.length ? "Select vehicle" : "No vehicles added yet"}</option>
            {choosable.map((v) => (
              <option key={v.id} value={v.id}>
                {v.plate_number}{v.route_name ? ` · ${v.route_name}` : ""}
              </option>
            ))}
          </select>
        </label>
      </div>

      {vehicle && (
        <>
          <div className="card">
            <div className="item-head">
              <span className="item-title">{vehicle.plate_number}</span>
              {left == null ? (
                <span className="chip pending">Seats not set</span>
              ) : full ? (
                <span className="chip rejected">Full</span>
              ) : almostFull ? (
                <span className="chip pending">Almost full</span>
              ) : (
                <span className="chip">Seats available</span>
              )}
            </div>
            <div className="item-sub">Status: {statusLabel(vehicle.status)}</div>

            <div className="seat-board">
              <div>
                <div className="seat-number">{left ?? "?"}</div>
                <div className="muted">seats free of {total}</div>
              </div>
              <div>
                <div className="seat-number">{onBoard ?? "?"}</div>
                <div className="muted">passengers booked</div>
              </div>
            </div>
            <div className="meter" role="progressbar" aria-valuemin={0} aria-valuemax={total}
              aria-valuenow={onBoard ?? 0} aria-label="Seats taken">
              <div style={{ width: `${percentFull}%` }} />
            </div>
            {full && <p className="warning">The vehicle is full. Tell the station staff it is ready to depart.</p>}
          </div>

          <div className="card">
            <h2>Passengers</h2>
            <div className="stepper">
              <button type="button" className="secondary" aria-label="One fewer passenger"
                disabled={count <= 1} onClick={() => { setCount(count - 1); setError(""); }}>−</button>
              <span className="value" aria-live="polite">{plural(count, "passenger")}</span>
              <button type="button" className="secondary" aria-label="One more passenger"
                disabled={count >= total} onClick={() => { setCount(count + 1); setError(""); }}>+</button>
            </div>
            <div className="actions">
              <button className="full" disabled={busy || !!bookProblem} onClick={() => submit("book")}>
                Book {plural(count, "seat")}
              </button>
              <button className="secondary full" disabled={busy || !!cancelProblem} onClick={() => submit("cancel")}>
                Cancel {plural(count, "booking")}
              </button>
            </div>
            {bookProblem && left != null && <p className="hint" style={{ marginBottom: 0 }}>{bookProblem}</p>}
          </div>

          {log.length > 0 && (
            <>
              <h2>This session</h2>
              <div className="list">
                {log.map((entry, i) => (
                  <div className="item" key={i}>
                    <div className="item-sub" style={{ marginTop: 0 }}>{entry.time.toLocaleTimeString()}</div>
                    <div>{entry.text}</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
      <LastUpdated value={lastUpdated} />
    </>
  );
}
