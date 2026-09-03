import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  type PlacedResult,
  type TicketId,
  uid,
} from "../lib/protocol";
import { storage } from "../lib/storage";

export function Results() {
  const [rows, setRows] = useState<PlacedResult[]>(() => storage.results.load());
  const [confirmPlaced, setConfirmPlaced] = useState(false);
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    sport: "WNBA",
    ticket: "A" as TicketId,
    legs: "",
    stake: 50,
    odds: "",
    notes: "",
  });

  useEffect(() => {
    storage.results.save(rows);
  }, [rows]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!confirmPlaced) return;
    if (!form.legs.trim()) return;
    const row: PlacedResult = {
      id: uid(),
      date: form.date,
      sport: form.sport,
      ticket: form.ticket,
      legs: form.legs.trim(),
      stake: form.stake,
      odds: form.odds,
      status: "pending",
      notes: form.notes,
    };
    setRows((prev) => [row, ...prev]);
    setConfirmPlaced(false);
    setForm((f) => ({ ...f, legs: "", odds: "", notes: "" }));
  }

  function setStatus(id: string, status: PlacedResult["status"]) {
    setRows((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status } : r)),
    );
  }

  function remove(id: string) {
    setRows((prev) => prev.filter((r) => r.id !== id));
  }

  return (
    <div className="page">
      <header className="page-head">
        <h1>Results</h1>
        <p>
          Log only after you confirm the wager is placed. Pending until you
          grade win / loss.
        </p>
      </header>

      <div className="grid-2">
        <section className="panel">
          <h2>Log placed ticket</h2>
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="date">Date</label>
              <input
                id="date"
                type="date"
                value={form.date}
                onChange={(e) =>
                  setForm((f) => ({ ...f, date: e.target.value }))
                }
                required
              />
            </div>
            <div className="field">
              <label htmlFor="sport">Sport</label>
              <select
                id="sport"
                value={form.sport}
                onChange={(e) =>
                  setForm((f) => ({ ...f, sport: e.target.value }))
                }
              >
                {["WNBA", "MLB", "NBA", "NFL", "NHL", "Other"].map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="ticket">Ticket</label>
              <select
                id="ticket"
                value={form.ticket}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    ticket: e.target.value as TicketId,
                  }))
                }
              >
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C Fortress</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="legs">Legs (one per line or comma-separated)</label>
              <textarea
                id="legs"
                value={form.legs}
                onChange={(e) =>
                  setForm((f) => ({ ...f, legs: e.target.value }))
                }
                placeholder="Howard 6+ REB&#10;Iriafen 6+ REB"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="stake">Stake ($)</label>
              <input
                id="stake"
                type="number"
                min={1}
                step="1"
                value={form.stake}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    stake: Number(e.target.value) || 0,
                  }))
                }
              />
            </div>
            <div className="field">
              <label htmlFor="odds">Ticket odds / payout</label>
              <input
                id="odds"
                value={form.odds}
                onChange={(e) =>
                  setForm((f) => ({ ...f, odds: e.target.value }))
                }
                placeholder="+273 / $126.51"
              />
            </div>
            <div className="field">
              <label htmlFor="notes">Notes</label>
              <textarea
                id="notes"
                value={form.notes}
                onChange={(e) =>
                  setForm((f) => ({ ...f, notes: e.target.value }))
                }
              />
            </div>
            <div className="field">
              <label>
                <input
                  type="checkbox"
                  checked={confirmPlaced}
                  onChange={(e) => setConfirmPlaced(e.target.checked)}
                />{" "}
                I confirm this wager is placed
              </label>
            </div>
            <button
              className="btn btn-primary"
              type="submit"
              disabled={!confirmPlaced}
            >
              Save result
            </button>
          </form>
        </section>

        <section className="panel">
          <h2>Ledger</h2>
          {rows.length === 0 ? (
            <p className="empty">No placed tickets logged yet.</p>
          ) : (
            <table className="results-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Ticket</th>
                  <th>Legs</th>
                  <th>Stake</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>
                      {r.date}
                      <br />
                      <span style={{ color: "var(--mute)" }}>{r.sport}</span>
                    </td>
                    <td>{r.ticket}</td>
                    <td style={{ whiteSpace: "pre-wrap", maxWidth: 220 }}>
                      {r.legs}
                      {r.odds ? (
                        <>
                          <br />
                          <span style={{ color: "var(--gold)" }}>{r.odds}</span>
                        </>
                      ) : null}
                    </td>
                    <td>${r.stake}</td>
                    <td>
                      <select
                        value={r.status}
                        onChange={(e) =>
                          setStatus(
                            r.id,
                            e.target.value as PlacedResult["status"],
                          )
                        }
                        style={{
                          background: "var(--ink-2)",
                          border: "1px solid var(--line)",
                          padding: "0.35rem",
                        }}
                      >
                        <option value="pending">pending</option>
                        <option value="win">win</option>
                        <option value="loss">loss</option>
                      </select>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => remove(r.id)}
                      >
                        Del
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}
