import { Link } from "react-router-dom";

export function Home() {
  return (
    <section className="hero">
      <div className="hero-plane" aria-hidden />
      <div className="hero-content">
        <h1 className="hero-brand">YWP OS</h1>
        <p className="hero-tag">The Underdog Strategist</p>
        <p className="hero-lede">
          Triple-Ticket Cushion Protocol. Floor at YIS 80. Cushion over hit rate.
          Results only after you confirm placed.
        </p>
        <div className="cta-row">
          <Link className="btn btn-primary" to="/protocol">
            Open protocol
          </Link>
          <Link className="btn btn-ghost" to="/results">
            Results log
          </Link>
        </div>
      </div>
    </section>
  );
}
