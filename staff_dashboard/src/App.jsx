import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import NavBar from "./components/NavBar";
import Queue from "./pages/Queue";
import Vehicles from "./pages/Vehicles";
import Trips from "./pages/Trips";

export default function App() {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem("user") || "null"));

  function handleLogin(u) {
    localStorage.setItem("user", JSON.stringify(u));
    localStorage.setItem("token", u.token);
    setUser(u);
  }

  function handleLogout() {
    localStorage.removeItem("user");
    localStorage.removeItem("token");
    setUser(null);
  }

  if (!user) return <Login onLogin={handleLogin} />;

  return (
    <BrowserRouter>
      <NavBar user={user} onLogout={handleLogout} />
      <main className="page">
        <Routes>
          <Route path="/queue" element={<Queue />} />
          <Route path="/vehicles" element={<Vehicles />} />
          <Route path="/trips" element={<Trips />} />
          <Route path="*" element={<Navigate to="/queue" />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
