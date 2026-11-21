import { useState } from "react";
import { api } from "../api";

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!email || !password) {
      setError("Please enter your email and password");
      return;
    }
    try {
      const user = await api.login(email, password);
      onLogin(user);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="login card">
      <form onSubmit={handleSubmit}>
        <h1>Staff sign in</h1>
        <label>
          Email
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit">Sign in</button>
      </form>
      <p className="muted">Demo: demo@station.com / demo123</p>
    </div>
  );
}
