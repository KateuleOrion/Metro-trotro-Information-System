import { useState } from "react";
import { Link } from "react-router-dom";
import { api, isDemoMode } from "../api";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Please enter your email and password");
      return;
    }
    setBusy(true);
    try {
      const user = await api.login(email, password);
      onLogin(user);
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  }

  return (
    <main className="page public">
      <div className="brand">
        <span className="logo">MT</span>
        <h1>Metro Trotro</h1>
        <p className="muted">Station staff</p>
      </div>
      <div className="card">
        <form className="stack" onSubmit={handleSubmit}>
          <h2>Sign in</h2>
          <label>
            Email
            <input type="email" inputMode="email" autoComplete="username" value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            Password
            <input type="password" autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button type="submit" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
        </form>
        <p className="muted center">
          Demo: demo@station.com / demo123{isDemoMode ? " (demo mode)" : ""}
        </p>
      </div>
      <p className="center">
        Are you a driver? <Link to="/driver-register">Ask to be registered</Link>
      </p>
    </main>
  );
}
