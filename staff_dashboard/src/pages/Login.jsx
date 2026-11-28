import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api, isDemoMode } from "../api";

// Log in or register as a driver, mate (conductor), station staff or a station manager.
// Every role uses this same page and the same login; drivers can also register their vehicle.
// Accounts use a phone number, or an email instead. Logging in uses whichever one was registered.
const ROLES = {
  driver: { role: "driver", title: "Driver", demo: { phone: "0240000001", password: "driver123" }, phoneOnly: true },
  mate: { role: "mate", title: "Mate", demo: { phone: "0200000004", password: "mate123" } },
  staff: { role: "station_staff", title: "Station staff", demo: { phone: "0200000002", password: "staff123" } },
  manager: { role: "station_manager", title: "Station manager", demo: { phone: "0200000001", password: "demo123" } },
};
const PHONE = /^\+?[0-9][0-9 -]{6,19}$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const blank = { name: "", phone: "", email: "", password: "", confirm: "",
  withVehicle: false, plate: "", destination: "", seats: "" };

export default function Login({ onLogin }) {
  const { role: key } = useParams();
  const role = ROLES[key];
  const [tab, setTab] = useState("login");
  const [useEmail, setUseEmail] = useState(false); // phone number by default, email as the alternative
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [form, setForm] = useState(blank);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [routes, setRoutes] = useState([]); // destination suggestions for drivers

  useEffect(() => {
    if (key === "driver") api.getRoutes().then(setRoutes).catch(() => {});
  }, [key]);

  if (!role) return <Navigate to="/" />;

  const set = (field) => (e) =>
    setForm({ ...form, [field]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  function switchTab(next) {
    setTab(next);
    setError("");
    setNotice("");
  }

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    if (!loginId.trim() || !password) {
      setError(`Please enter your ${useEmail ? "email" : "phone number"} and password`);
      return;
    }
    setBusy(true);
    try {
      onLogin(await api.login(loginId.trim(), password, role.role)); // only accounts of the chosen role
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  }

  function checkRegistration() {
    if (form.name.trim().length < 2) return "Please enter your full name";
    if (useEmail ? !EMAIL.test(form.email.trim()) : !PHONE.test(form.phone.trim()))
      return useEmail ? "Please enter a valid email" : "Please enter a valid phone number";
    if (form.password.length < 8) return "The password must be at least 8 characters";
    if (form.password !== form.confirm) return "The two passwords do not match";
    if (form.withVehicle) {
      if (!form.plate.trim()) return "Please enter your vehicle's registration number";
      if (!form.destination.trim()) return "Please enter where your vehicle goes";
      const seats = Number(form.seats);
      if (!Number.isInteger(seats) || seats < 1 || seats > 100) return "Number of seats must be a whole number from 1 to 100";
    }
    return "";
  }

  async function handleRegister(e) {
    e.preventDefault();
    const problem = checkRegistration();
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    try {
      const res = await api.register({
        name: form.name.trim(),
        role: role.role,
        phone: useEmail ? null : form.phone.trim(),
        email: useEmail ? form.email.trim() : null,
        password: form.password,
        ...(form.withVehicle
          ? { plate: form.plate.trim(), destination: form.destination.trim(), seats: Number(form.seats) }
          : {}),
      });
      if (res.account_status === "active" && res.token) {
        onLogin(res);
      } else {
        setLoginId(useEmail ? form.email.trim() : form.phone.trim());
        setPassword("");
        setForm(blank);
        setTab("login");
        setError("");
        setNotice("Account created. The station manager must approve it before you can log in.");
      }
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  }

  const idLabel = useEmail ? "Email" : "Phone number";
  const switchId = role.phoneOnly ? null : (
    <button type="button" className="link" onClick={() => { setUseEmail(!useEmail); setError(""); }}>
      {useEmail ? "Use phone number instead" : "Use email instead"}
    </button>
  );

  return (
    <main className="page public">
      <div className="brand">
        <span className="logo">MT</span>
        <h1>{role.title}</h1>
        <p className="muted">Metro Trotro station</p>
      </div>

      <div className="segments" role="tablist">
        <button role="tab" aria-selected={tab === "login"} className={tab === "login" ? "on" : ""}
          onClick={() => switchTab("login")}>Log in</button>
        <button role="tab" aria-selected={tab === "register"} className={tab === "register" ? "on" : ""}
          onClick={() => switchTab("register")}>Register</button>
      </div>

      {notice && <p className="notice" role="status">{notice}</p>}

      <div className="card">
        {tab === "login" ? (
          <form className="stack" onSubmit={handleLogin}>
            <div className="field">
              <label>
              {idLabel}
              <input type={useEmail ? "email" : "tel"} inputMode={useEmail ? "email" : "tel"} autoComplete="username"
                placeholder={useEmail ? "you@example.com" : "e.g. 0241234567"}
                value={loginId} onChange={(e) => setLoginId(e.target.value)} />
              </label>
              <span className="hint">Use the {useEmail ? "email" : "phone number"} you registered with. {switchId}</span>
            </div>
            <label>
              Password
              <input type="password" autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} />
            </label>
            {error && <p className="error" role="alert">{error}</p>}
            <button type="submit" disabled={busy}>{busy ? "Logging in..." : "Log in"}</button>
            <p className="muted center hint">
              Demo: {role.demo.phone} / {role.demo.password}{isDemoMode ? " (demo mode)" : ""}{" "}
              <button type="button" className="link" onClick={() => {
                setUseEmail(false);
                setLoginId(role.demo.phone);
                setPassword(role.demo.password);
                setError("");
              }}>Fill in</button>
            </p>
          </form>
        ) : (
          <form className="stack" onSubmit={handleRegister}>
            <label>
              Full name
              <input value={form.name} onChange={set("name")} autoComplete="name" />
            </label>
            <div className="field">
              <label>
              {idLabel}
              {useEmail ? (
                <input type="email" inputMode="email" autoComplete="email" placeholder="you@example.com"
                  value={form.email} onChange={set("email")} />
              ) : (
                <input type="tel" inputMode="tel" autoComplete="tel" placeholder="e.g. 0241234567"
                  value={form.phone} onChange={set("phone")} />
              )}
              </label>
              <span className="hint">You will log in with this. {switchId}</span>
            </div>
            <div className="field">
              <label>
              Password
              <input type="password" autoComplete="new-password" value={form.password} onChange={set("password")} />
              </label>
              <span className="hint">At least 8 characters.</span>
            </div>
            <label>
              Confirm password
              <input type="password" autoComplete="new-password" value={form.confirm} onChange={set("confirm")} />
            </label>
            {key === "driver" && (
              <>
                <label className="check">
                  <input type="checkbox" checked={form.withVehicle} onChange={set("withVehicle")} />
                  I also want to register my vehicle
                </label>
                {form.withVehicle && (
                  <>
                    <label>
                      Registration number
                      <input value={form.plate} onChange={set("plate")} placeholder="e.g. GR-1234-24" autoCapitalize="characters" />
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
              </>
            )}
            {error && <p className="error" role="alert">{error}</p>}
            <button type="submit" disabled={busy}>{busy ? "Creating account..." : "Create account"}</button>
            <p className="muted center hint">New accounts may need a station manager's approval before you can log in.</p>
          </form>
        )}
      </div>

      <p className="center"><Link to="/">Choose a different role</Link></p>
    </main>
  );
}
