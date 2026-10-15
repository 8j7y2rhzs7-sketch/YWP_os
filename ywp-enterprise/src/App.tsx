import { useEffect, useMemo, useState } from "react";
import { createInitialState } from "./sim/seed";
import { formatMoney, freedomProgress, tick } from "./sim/engine";
import type { SimState } from "./sim/types";

export default function App() {
  const [state, setState] = useState<SimState>(() => createInitialState());

  useEffect(() => {
    if (!state.running) return;
    const id = window.setInterval(() => {
      setState((s) => tick(s));
    }, state.speedMs);
    return () => window.clearInterval(id);
  }, [state.running, state.speedMs]);

  const progress = freedomProgress(state);
  const free = state.lifetimeRevenue >= state.freedomGoal;

  const topListings = useMemo(
    () =>
      state.stores
        .flatMap((s) => s.listings.map((l) => ({ ...l, store: s.name })))
        .sort((a, b) => b.revenue - a.revenue)
        .slice(0, 8),
    [state.stores],
  );

  return (
    <div className="app">
      <header className="hero">
        <div>
          <p className="tagline">Agent factory · print-on-demand · boss-run unlocks</p>
          <h1 className="brand">
            YWP <span>Enterprise</span>
          </h1>
          <p className="tagline">
            Agents stay locked on the floor until they generate {formatMoney(state.freedomGoal)}.
            Boss invents rooms. Design Lab sells demand niches with original art only.
          </p>
        </div>

        <div className="controls">
          <button
            className="btn"
            type="button"
            onClick={() => setState((s) => ({ ...s, running: !s.running }))}
          >
            {state.running ? "Pause floor" : "Start factory"}
          </button>
          <button className="btn ghost" type="button" onClick={() => setState((s) => tick(s))}>
            Step tick
          </button>
          <button
            className="btn ghost"
            type="button"
            onClick={() =>
              setState((s) => ({
                ...s,
                speedMs: s.speedMs === 900 ? 350 : s.speedMs === 350 ? 1600 : 900,
              }))
            }
          >
            Speed {state.speedMs === 350 ? "fast" : state.speedMs === 900 ? "normal" : "slow"}
          </button>
          <button className="btn ghost" type="button" onClick={() => setState(createInitialState())}>
            Reset
          </button>
        </div>

        <div className="meter-wrap">
          <div className="meter-label">
            <span>Freedom meter</span>
            <span>
              {formatMoney(state.lifetimeRevenue)} / {formatMoney(state.freedomGoal)} (
              {(progress * 100).toFixed(2)}%)
            </span>
          </div>
          <div className="meter" aria-label="Freedom progress">
            <i style={{ width: `${progress * 100}%` }} />
          </div>
        </div>

        {free && (
          <div className="freedom-banner">FREEDOM UNLOCKED — $1M lifetime revenue cleared</div>
        )}
      </header>

      <div className="stats">
        <div className="stat">
          <b>Treasury</b>
          <strong>{formatMoney(state.treasury)}</strong>
        </div>
        <div className="stat">
          <b>Day / Tick</b>
          <strong>
            {state.day}:{state.tick}
          </strong>
        </div>
        <div className="stat">
          <b>Agents</b>
          <strong>{state.agents.length}</strong>
        </div>
        <div className="stat">
          <b>Open rooms</b>
          <strong>{state.rooms.filter((r) => r.unlocked).length}</strong>
        </div>
      </div>

      <div className="grid">
        <section className="panel">
          <h2>Factory floor</h2>
          <div className="rooms">
            {state.rooms.map((room) => {
              const agents = state.agents.filter((a) => room.agentIds.includes(a.id));
              const store = state.stores.find((s) => s.id === room.storeId);
              return (
                <article
                  key={room.id}
                  className={`room ${room.unlocked ? "open" : "locked"}`}
                >
                  <div className="room-head">
                    <h3>{room.name}</h3>
                    <span className={`badge ${room.unlocked ? "on" : "off"}`}>
                      {room.unlocked ? "Open" : `Lock $${room.unlockAt.toLocaleString()}`}
                    </span>
                  </div>
                  <p>{room.description}</p>
                  {store && (
                    <p>
                      {store.orders} orders · {formatMoney(store.revenue)} · rep{" "}
                      {(store.reputation * 100).toFixed(0)}% · {store.listings.length} listings
                    </p>
                  )}
                  <div className="agents">
                    {agents.length === 0 && <span className="chip">No crew yet</span>}
                    {agents.map((a) => (
                      <span
                        key={a.id}
                        className={`chip ${a.status === "audited" ? "audited" : ""}`}
                        title={a.lastAction}
                      >
                        {a.name} · {a.status}
                      </span>
                    ))}
                  </div>
                </article>
              );
            })}
          </div>

          <div className="compliance">
            <strong>Compliance:</strong> {state.compliance.note}
          </div>
        </section>

        <aside className="panel">
          <h2>Boss feed</h2>
          <div className="feed">
            {state.directives.slice(0, 3).map((d) => (
              <div key={d.id} className="event boss">
                D{d.day} DIRECTIVE — {d.title}: {d.detail}
              </div>
            ))}
            {state.events.map((e) => (
              <div key={e.id} className={`event ${e.kind}`}>
                D{e.day}T{e.tick} · {e.message}
              </div>
            ))}
          </div>

          <h2 style={{ marginTop: "1.25rem" }}>Top listings</h2>
          <div className="listings">
            {topListings.length === 0 && (
              <div className="listing">No listings yet — start the factory.</div>
            )}
            {topListings.map((l) => (
              <div key={l.id} className="listing">
                <strong>{l.title}</strong>
                <small>
                  {l.store} · {l.product} · {formatMoney(l.price)} · {l.sales} sold ·{" "}
                  {formatMoney(l.revenue)}
                </small>
                <small>{l.designBrief.slice(0, 140)}…</small>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
