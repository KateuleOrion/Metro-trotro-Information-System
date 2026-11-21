import { NavLink } from "react-router-dom";

export default function NavBar({ user, onLogout }) {
  return (
    <nav>
      <strong>Station information</strong>
      <NavLink to="/queue">Queue</NavLink>
      <NavLink to="/vehicles">Vehicles</NavLink>
      <NavLink to="/trips">Trips</NavLink>
      <span className="spacer" />
      <span className="muted">{user.name}</span>
      <button className="secondary" onClick={onLogout}>Sign out</button>
    </nav>
  );
}
