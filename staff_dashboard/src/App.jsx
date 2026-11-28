import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import RoleChoice from "./pages/RoleChoice";
import NavBar from "./components/NavBar";
import Queue from "./pages/Queue";
import Vehicles from "./pages/Vehicles";
import Trips from "./pages/Trips";
import MapPage from "./pages/Map";
import Mate from "./pages/Mate";
import Requests from "./pages/Requests";
import DriverRegister from "./pages/DriverRegister";

export default function App() {
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem("user") || "null"));
  const isManager = user?.role === "station_manager";
  const isMate = user?.role === "mate";

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

  return (
    <BrowserRouter>
      <Routes>
        {/* Public page: a driver asks to be registered. No sign-in needed. */}
        <Route path="/driver-register" element={<DriverRegister />} />

        {user && isMate ? (
          // The mate's own app: only the seat booking screen, no staff tabs.
          <Route
            path="*"
            element={
              <>
                <NavBar user={user} onLogout={handleLogout} />
                <main className="page">
                  <Routes>
                    <Route path="/mate" element={<Mate />} />
                    <Route path="*" element={<Navigate to="/mate" />} />
                  </Routes>
                </main>
              </>
            }
          />
        ) : !user ? (
          <>
            {/* Everyone starts here: choose Passenger, Driver, Mate, Station staff or Station manager. */}
            <Route path="/" element={<RoleChoice />} />
            <Route path="/account/:role" element={<Login onLogin={handleLogin} />} />
            <Route path="*" element={<Navigate to="/" />} />
          </>
        ) : (
          <Route
            path="*"
            element={
              <>
                <NavBar user={user} onLogout={handleLogout} />
                <main className="page">
                  <Routes>
                    <Route path="/queue" element={<Queue />} />
                    <Route path="/vehicles" element={<Vehicles user={user} />} />
                    <Route path="/trips" element={<Trips />} />
                    <Route path="/map" element={<MapPage user={user} />} />
                    {isManager && <Route path="/requests" element={<Requests />} />}
                    <Route path="*" element={<Navigate to="/queue" />} />
                  </Routes>
                </main>
              </>
            }
          />
        )}
      </Routes>
    </BrowserRouter>
  );
}
