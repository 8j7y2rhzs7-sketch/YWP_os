import { NavLink, Route, Routes } from "react-router-dom";
import { Nav } from "./components/Nav";
import { Home } from "./pages/Home";
import { Protocol } from "./pages/Protocol";
import { Results } from "./pages/Results";

export default function App() {
  return (
    <div className="app-shell">
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/protocol" element={<Protocol />} />
          <Route path="/results" element={<Results />} />
        </Routes>
      </main>
      <footer className="footer">
        <span>YWP OS · Triple-Ticket Cushion</span>
        <span>
          <NavLink to="/protocol">Protocol locked</NavLink>
        </span>
      </footer>
    </div>
  );
}
