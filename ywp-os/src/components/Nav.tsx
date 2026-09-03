import { NavLink } from "react-router-dom";

export function Nav() {
  return (
    <header className="nav">
      <NavLink to="/" className="nav-brand">
        YWP OS<span>Underdog Strategist</span>
      </NavLink>
      <nav className="nav-links">
        <NavLink to="/" end>
          Home
        </NavLink>
        <NavLink to="/protocol">Protocol</NavLink>
        <NavLink to="/results">Results</NavLink>
      </nav>
    </header>
  );
}
