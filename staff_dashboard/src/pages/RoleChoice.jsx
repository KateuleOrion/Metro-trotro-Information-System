import { useState } from "react";
import { Link } from "react-router-dom";

// The first screen everyone sees: choose who you are, then log in or register.
// Passengers use their own phone app, so their card only says where to go.
const ROLES = [
  { key: "passenger", title: "Passenger",
    note: "Passengers do not need an account. Open the Metro Trotro passenger app to search for a vehicle to your destination and see how many seats are free." },
  { key: "driver", title: "Driver", to: "/account/driver" },
  { key: "mate", title: "Mate", to: "/account/mate" },
  { key: "staff", title: "Station staff", to: "/account/staff" },
  { key: "manager", title: "Station manager", to: "/account/manager" },
];

export default function RoleChoice() {
  const [open, setOpen] = useState(null); // which card's note is showing

  return (
    <main className="page public">
      <div className="brand">
        <span className="logo">MT</span>
        <h1>Metro Trotro</h1>
        <p className="muted">Who are you?</p>
      </div>

      <div className="list">
        {ROLES.map((r) =>
          r.to ? (
            <Link key={r.key} to={r.to} className="item role-card">
              <span className="item-title">{r.title}</span>
            </Link>
          ) : (
            <div key={r.key}>
              <button type="button" className="item role-card" aria-expanded={open === r.key}
                onClick={() => setOpen(open === r.key ? null : r.key)}>
                <span className="item-title">{r.title}</span>
              </button>
              {open === r.key && <p className="notice role-note" role="status">{r.note}</p>}
            </div>
          )
        )}
      </div>
    </main>
  );
}
