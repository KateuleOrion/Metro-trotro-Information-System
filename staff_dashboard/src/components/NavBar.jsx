import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { api } from "../api";

// Small line icons for the bottom tab bar.
const Icon = ({ d }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true">
    {d.map((p, i) => <path key={i} d={p} />)}
  </svg>
);
const ICONS = {
  queue: ["M8 6h13", "M8 12h13", "M8 18h13", "M3 6h.01", "M3 12h.01", "M3 18h.01"],
  vehicles: ["M4 16V7a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v9", "M3 16h18v2a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z", "M4 11h16", "M7 19v2", "M17 19v2"],
  trips: ["M12 7v5l3 2", "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"],
  map: ["M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z", "M12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z"],
  requests: ["M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", "M19 8v6", "M22 11h-6"],
};

const TITLES = { "/queue": "Vehicle queue", "/vehicles": "Vehicles", "/trips": "Trips", "/map": "Live map", "/requests": "Requests" };

export default function NavBar({ user, onLogout }) {
  const isManager = user?.role === "station_manager";
  const { pathname } = useLocation();
  const [pending, setPending] = useState(0);

  // The manager sees how many driver requests are waiting, refreshed every 30 seconds.
  useEffect(() => {
    if (!isManager) return;
    // waiting driver requests + waiting station staff / manager accounts
    const load = () =>
      Promise.all([api.getDriverRequests("pending"), api.getStaffAccounts("pending")])
        .then(([d, s]) => setPending(d.length + s.length))
        .catch(() => {});
    load();
    const timer = setInterval(load, 30000);
    window.addEventListener("driver-requests-changed", load);
    return () => {
      clearInterval(timer);
      window.removeEventListener("driver-requests-changed", load);
    };
  }, [isManager]);

  const tabs = [
    { to: "/queue", label: "Queue", icon: "queue" },
    { to: "/vehicles", label: "Vehicles", icon: "vehicles" },
    { to: "/trips", label: "Trips", icon: "trips" },
    { to: "/map", label: "Map", icon: "map" },
    ...(isManager ? [{ to: "/requests", label: "Requests", icon: "requests", count: pending }] : []),
  ];

  return (
    <>
      <header className="topbar">
        <span className="heading">
          <span className="title">{TITLES[pathname] ?? "Station information"}</span>
          <span className="who">{user.name}</span>
        </span>
        <button onClick={onLogout}>Sign out</button>
      </header>
      <nav className="tabbar" aria-label="Main">
        <div className="tabbar-inner">
          {tabs.map((t) => (
            <NavLink key={t.to} to={t.to}>
              <Icon d={ICONS[t.icon]} />
              {t.label}
              {t.count > 0 && <span className="badge" aria-label={`${t.count} waiting`}>{t.count}</span>}
            </NavLink>
          ))}
        </div>
      </nav>
    </>
  );
}
