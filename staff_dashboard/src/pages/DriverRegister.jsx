import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

// Public page (no sign-in): a driver asks the station manager to register them.
const empty = { name: "", phone: "", withVehicle: false, plate: "", destination: "", seats: "" };
const PHONE = /^[0-9+ ]{7,20}$/;

const STATUS_TEXT = {
  pending: "Waiting for the station manager",
  approved: "Approved. You are registered at the station",
  rejected: "Not approved",
};

function validate(f) {
  if (f.name.trim().length < 2) return "Please enter your full name";
  if (!PHONE.test(f.phone.trim())) return "Please enter a valid phone number (digits, spaces and + only)";
  if (f.withVehicle) {
    if (!f.plate.trim()) return "Please enter your vehicle's registration number";
    if (!f.destination.trim()) return "Please enter where your vehicle goes";
    const seats = Number(f.seats);
    if (!Number.isInteger(seats) || seats < 1 || seats > 100) return "Number of seats must be a whole number from 1 to 100";
  }
  return "";
}

export default function DriverRegister() {
  const [form, setForm] = useState(empty);
  const [routes, setRoutes] = useState([]);
  const [sent, setSent] = useState(null); // { id, name }
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [checkPhone, setCheckPhone] = useState("");
  const [status, setStatus] = useState(null);
  const [checkError, setCheckError] = useState("");

  useEffect(() => {
    api.getRoutes().then(setRoutes).catch(() => {}); // only used for destination suggestions
  }, []);

  const set = (field) => (e) =>
    setForm({ ...form, [field]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  async function handleSubmit(e) {
    e.preventDefault();
    const problem = validate(form);
    if (problem) return setError(problem);
    setBusy(true);
    try {
      const r = await api.submitDriverRequest({
        name: form.name.trim(),
        phone: form.phone.trim(),
        ...(form.withVehicle
          ? { plate: form.plate.trim(), destination: form.destination.trim(), seats: Number(form.seats) }
          : {}),
      });
      setSent({ id: r.id, name: form.name.trim() });
      setCheckPhone(form.phone.trim());
      setForm(empty);
      setError("");
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  }

  async function handleCheck(e) {
    e.preventDefault();
    if (!PHONE.test(checkPhone.trim())) return setCheckError("Please enter the phone number you used");
    try {
      setStatus(await api.getDriverRequestStatus(checkPhone.trim()));
      setCheckError("");
    } catch (err) {
      setStatus(null);
      setCheckError(err.message);
    }
  }

  return (
    <main className="page public">
      <div className="brand">
        <span className="logo">MT</span>
        <h1>Driver registration</h1>
        <p className="muted">Metro Central Station</p>
      </div>

      {sent ? (
        <div className="card">
          <p className="notice" role="status">
            Thank you, {sent.name}. Your request (number {sent.id}) has been sent to the station manager.
          </p>
          <p>You can check below whether it has been approved.</p>
          <button className="secondary" onClick={() => setSent(null)}>Send another request</button>
        </div>
      ) : (
        <div className="card">
          <h2>Ask to be registered</h2>
          <form className="stack" onSubmit={handleSubmit}>
            <label>
              Full name
              <input value={form.name} onChange={set("name")} autoComplete="name" />
            </label>
            <label>
              Phone number
              <input type="tel" inputMode="tel" value={form.phone} onChange={set("phone")}
                placeholder="e.g. 0241234567" autoComplete="tel" />
              <span className="hint">The station manager may call you on this number.</span>
            </label>
            <label className="check">
              <input type="checkbox" checked={form.withVehicle} onChange={set("withVehicle")} />
              I also want to register my vehicle
            </label>
            {form.withVehicle && (
              <>
                <label>
                  Registration number
                  <input value={form.plate} onChange={set("plate")} placeholder="e.g. GR-1234-24"
                    autoCapitalize="characters" />
                </label>
                <label>
                  Destination
                  <input list="driver-destinations" value={form.destination} onChange={set("destination")}
                    placeholder="e.g. Madina" autoComplete="off" />
                  <datalist id="driver-destinations">
                    {[...new Set(routes.map((r) => r.to))].map((n) => <option key={n} value={n} />)}
                  </datalist>
                </label>
                <label>
                  Number of seats
                  <input type="number" inputMode="numeric" min="1" max="100" value={form.seats} onChange={set("seats")} />
                </label>
              </>
            )}
            {error && <p className="error" role="alert">{error}</p>}
            <button type="submit" disabled={busy}>{busy ? "Sending..." : "Send request"}</button>
          </form>
        </div>
      )}

      <div className="card">
        <h2>Check your request</h2>
        <form className="stack" onSubmit={handleCheck}>
          <input type="tel" inputMode="tel" aria-label="Phone number used for the request"
            placeholder="Phone number you used" value={checkPhone} onChange={(e) => setCheckPhone(e.target.value)} />
          <button type="submit" className="secondary">Check status</button>
        </form>
        {checkError && <p className="error" role="alert" style={{ marginTop: 12 }}>{checkError}</p>}
        {status && (
          <div style={{ marginTop: 12 }}>
            <span className={`chip ${status.status}`}>{STATUS_TEXT[status.status]}</span>
            <p className="muted">Request number {status.id}, sent {new Date(status.submitted_at).toLocaleString()}</p>
            {status.reason && <p>Reason: {status.reason}</p>}
          </div>
        )}
      </div>

      <p className="center"><Link to="/">Choose a different role</Link></p>
    </main>
  );
}
