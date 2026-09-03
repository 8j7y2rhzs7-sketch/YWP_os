import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { sampleLegs } from "../data/sampleSlate";
import {
  PHASES,
  PRIORITY,
  scoreLeg,
  type LegInput,
  type ScoredLeg,
  type TicketId,
  type TicketState,
  uid,
} from "../lib/protocol";
import { storage } from "../lib/storage";

const emptyForm = (): Omit<LegInput, "id"> => ({
  player: "",
  market: "PTS",
  line: "",
  odds: "",
  cushion: 2,
  l5Avg: 0,
  l5Floor: 0,
  misses: 0,
  scriptFit: 10,
  roleClarity: 10,
  injuryRisk: 0,
  correlationDrag: 0,
  unresolvedFlag: false,
});

export function Protocol() {
  const [legs, setLegs] = useState<LegInput[]>(() =>
    storage.legs.load<LegInput[]>([]),
  );
  const [tickets, setTickets] = useState<TicketState>(() =>
    storage.tickets.load({ A: [], B: [], C: [] }),
  );
  const [active, setActive] = useState<TicketId>("A");
  const [form, setForm] = useState(emptyForm);

  useEffect(() => {
    storage.legs.save(legs);
  }, [legs]);

  useEffect(() => {
    storage.tickets.save(tickets);
  }, [tickets]);

  const scored: ScoredLeg[] = useMemo(() => legs.map(scoreLeg), [legs]);

  const ticketLegs = useMemo(() => {
    const ids = new Set(tickets[active]);
    return scored.filter((l) => ids.has(l.id));
  }, [scored, tickets, active]);

  const floorOk =
    ticketLegs.length === 0 ||
    ticketLegs.every((l) => l.yis >= 80 && !l.unresolvedFlag);

  const avgYis =
    ticketLegs.length === 0
      ? 0
      : Math.round(
          ticketLegs.reduce((s, l) => s + l.yis, 0) / ticketLegs.length,
        );

  function onAdd(e: FormEvent) {
    e.preventDefault();
    if (!form.player.trim() || !form.line.trim()) return;
    setLegs((prev) => [...prev, { ...form, id: uid() }]);
    setForm(emptyForm());
  }

  function seedDemo() {
    setLegs(sampleLegs());
    setTickets({ A: [], B: [], C: [] });
  }

  function clearAll() {
    setLegs([]);
    setTickets({ A: [], B: [], C: [] });
  }

  function toggleTicket(legId: string) {
    setTickets((prev) => {
      const on = prev[active].includes(legId);
      const nextIds = on
        ? prev[active].filter((id) => id !== legId)
        : [...prev[active], legId];
      return { ...prev, [active]: nextIds };
    });
  }

  function removeLeg(id: string) {
    setLegs((prev) => prev.filter((l) => l.id !== id));
    setTickets((prev) => ({
      A: prev.A.filter((x) => x !== id),
      B: prev.B.filter((x) => x !== id),
      C: prev.C.filter((x) => x !== id),
    }));
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>Triple-Ticket Protocol</h1>
        <p>
          Build Ticket A, B, and Fortress C. Parlay floor YIS ≥ 80. Never
          replace cut legs to preserve payout.
        </p>
        <div className="priority-bar">
          Priority: <em>{PRIORITY}</em>
        </div>
      </header>

      <div className="phase-strip">
        {PHASES.map((p) => (
          <div className="phase" key={p.n}>
            <strong>
              {p.n} · {p.title}
            </strong>
            {p.blurb}
          </div>
        ))}
      </div>

      <div className="grid-2">
        <section className="panel">
          <h2>Add leg</h2>
          <form onSubmit={onAdd}>
            <div className="field">
              <label htmlFor="player">Player / side</label>
              <input
                id="player"
                value={form.player}
                onChange={(e) =>
                  setForm((f) => ({ ...f, player: e.target.value }))
                }
                placeholder="e.g. Cardoso"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="market">Market</label>
              <select
                id="market"
                value={form.market}
                onChange={(e) =>
                  setForm((f) => ({ ...f, market: e.target.value }))
                }
              >
                {["PTS", "REB", "AST", "PRA", "Spread", "ML", "Total", "Other"].map(
                  (m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ),
                )}
              </select>
            </div>
            <div className="field">
              <label htmlFor="line">Line</label>
              <input
                id="line"
                value={form.line}
                onChange={(e) =>
                  setForm((f) => ({ ...f, line: e.target.value }))
                }
                placeholder="6+ / -2.5 / U8.5"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="odds">Odds</label>
              <input
                id="odds"
                value={form.odds}
                onChange={(e) =>
                  setForm((f) => ({ ...f, odds: e.target.value }))
                }
                placeholder="-115"
              />
            </div>
            <div className="field">
              <label htmlFor="cushion">Cushion (units under floor)</label>
              <input
                id="cushion"
                type="number"
                step="0.1"
                value={form.cushion}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    cushion: Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="field">
              <label htmlFor="l5Avg">L5 avg</label>
              <input
                id="l5Avg"
                type="number"
                step="0.1"
                value={form.l5Avg}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    l5Avg: Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="field">
              <label htmlFor="l5Floor">L5 floor</label>
              <input
                id="l5Floor"
                type="number"
                step="0.1"
                value={form.l5Floor}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    l5Floor: Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="field">
              <label htmlFor="misses">L5 misses</label>
              <input
                id="misses"
                type="number"
                value={form.misses}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    misses: Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="field">
              <label htmlFor="scriptFit">Script fit (0–15)</label>
              <input
                id="scriptFit"
                type="number"
                min={0}
                max={15}
                value={form.scriptFit}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    scriptFit: Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="field">
              <label htmlFor="roleClarity">Role clarity (0–15)</label>
              <input
                id="roleClarity"
                type="number"
                min={0}
                max={15}
                value={form.roleClarity}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    roleClarity: Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="field">
              <label htmlFor="injuryRisk">Injury risk (0–12)</label>
              <input
                id="injuryRisk"
                type="number"
                min={0}
                max={12}
                value={form.injuryRisk}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    injuryRisk: Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="field">
              <label htmlFor="corr">Correlation drag (0–10)</label>
              <input
                id="corr"
                type="number"
                min={0}
                max={10}
                value={form.correlationDrag}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    correlationDrag: Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="field">
              <label>
                <input
                  type="checkbox"
                  checked={form.unresolvedFlag}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      unresolvedFlag: e.target.checked,
                    }))
                  }
                />{" "}
                Unresolved P/Q flag
              </label>
            </div>
            <div className="row-actions">
              <button className="btn btn-primary" type="submit">
                Score leg
              </button>
              <button
                className="btn btn-ghost btn-sm"
                type="button"
                onClick={seedDemo}
              >
                Load demo slate
              </button>
              <button
                className="btn btn-danger btn-sm"
                type="button"
                onClick={clearAll}
              >
                Clear
              </button>
            </div>
          </form>
        </section>

        <section className="panel">
          <h2>Board · Ticket {active}</h2>
          <div className="ticket-tabs">
            {(["A", "B", "C"] as TicketId[]).map((t) => (
              <button
                key={t}
                type="button"
                className={`${active === t ? "active" : ""} ${t === "C" ? "fortress" : ""}`}
                onClick={() => setActive(t)}
              >
                {t === "C" ? "C Fortress" : `Ticket ${t}`}
              </button>
            ))}
          </div>

          <div className="ticket-summary">
            <span>
              Legs <strong>{ticketLegs.length}</strong>
            </span>
            <span>
              Avg YIS <strong>{ticketLegs.length ? avgYis : "—"}</strong>
            </span>
            <span>
              Floor{" "}
              <strong style={{ color: floorOk ? "var(--keep)" : "var(--cut)" }}>
                {ticketLegs.length === 0
                  ? "—"
                  : floorOk
                    ? "PASS ≥80"
                    : "FAIL"}
              </strong>
            </span>
          </div>

          {!floorOk && ticketLegs.length > 0 && (
            <p className="floor-warn">
              Parlay floor breach — remove HOLD/CUT or unresolved flags before
              locking Ticket {active}. Do not backfill cuts for payout.
            </p>
          )}

          {scored.length === 0 ? (
            <p className="empty">
              No legs yet. Add props or load the demo slate.
            </p>
          ) : (
            <ul className="leg-list">
              {scored.map((leg) => {
                const onTicket = tickets[active].includes(leg.id);
                const badge =
                  leg.verdict === "KEEP"
                    ? "badge-keep"
                    : leg.verdict === "HOLD"
                      ? "badge-hold"
                      : "badge-cut";
                return (
                  <li className="leg" key={leg.id}>
                    <div className="leg-main">
                      <strong>
                        {leg.player} · {leg.market} {leg.line}
                      </strong>
                      <span>
                        Odds {leg.odds || "—"} · Cushion {leg.cushion} · L5 avg{" "}
                        {leg.l5Avg} / floor {leg.l5Floor} · misses {leg.misses}
                        {leg.unresolvedFlag ? " · P/Q FLAG" : ""}
                      </span>
                    </div>
                    <div className="leg-meta">
                      <span className={`yis ${leg.yis < 80 ? "low" : ""}`}>
                        YIS {leg.yis}
                      </span>
                      <span className={`badge ${badge}`}>{leg.verdict}</span>
                      <button
                        type="button"
                        className={`btn btn-sm ${onTicket ? "btn-primary" : "btn-ghost"}`}
                        onClick={() => toggleTicket(leg.id)}
                        disabled={leg.verdict === "CUT" && !onTicket}
                        title={
                          leg.verdict === "CUT"
                            ? "CUT legs stay off tickets"
                            : undefined
                        }
                      >
                        {onTicket ? `On ${active}` : `Add ${active}`}
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => removeLeg(leg.id)}
                      >
                        Remove
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
