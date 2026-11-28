import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { api, isDemoMode } from "../api";

// Log in or register as a mate (conductor), station staff or a station manager.
// Accounts use a phone number, or an email instead. Logging in uses whichever one was registered.
const ROLES = {
  mate: { role: "mate", title: "Mate", demo: { phone: "0200000004", password: "mate123" } },
  staff: { role: "station_staff", title: "Station staff", demo: { phone: "0200000002", password: "staff123" } },
  manager: { role: "station_manager", title: "Station manager", demo: { phone: "0200000001", password: "demo123" } },
};
const PHONE = /^\+?[0-9][0-9 -]{6,19}$/;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const blank = { name: "", phone: "", email: "", password: "", confirm: "" };

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

  if (!role) return <Navigate to="/" />;

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

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
      onLogin(await api.login(loginId.trim(), password));
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
  const switchId = (
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
