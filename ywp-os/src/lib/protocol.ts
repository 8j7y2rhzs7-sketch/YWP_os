export type Verdict = "KEEP" | "HOLD" | "CUT";
export type TicketId = "A" | "B" | "C";

export interface LegInput {
  id: string;
  player: string;
  market: string;
  line: string;
  odds: string;
  cushion: number;
  l5Avg: number;
  l5Floor: number;
  misses: number;
  scriptFit: number;
  roleClarity: number;
  injuryRisk: number;
  correlationDrag: number;
  unresolvedFlag: boolean;
}

export interface ScoredLeg extends LegInput {
  yis: number;
  verdict: Verdict;
}

export interface TicketState {
  A: string[];
  B: string[];
  C: string[];
}

export interface PlacedResult {
  id: string;
  date: string;
  sport: string;
  ticket: TicketId;
  legs: string;
  stake: number;
  odds: string;
  status: "pending" | "win" | "loss";
  notes: string;
}

export const PHASES = [
  { n: "01", title: "Rotation sweep", blurb: "Full slate scan, minutes & usage" },
  { n: "02", title: "L5 / L10", blurb: "Avg, median, floor, misses, cushion" },
  { n: "03", title: "Matchup / H2H", blurb: "Defense rank & prior meetings" },
  { n: "04", title: "Game script", blurb: "Pace, spread, blowout risk" },
  { n: "05", title: "Role clarity", blurb: "Starter / board / minutes lock" },
  { n: "06", title: "Injury chain", blurb: "Who inherits usage" },
  { n: "07", title: "Cushion test", blurb: "Hard Rock alts vs main" },
  { n: "08", title: "Correlation", blurb: "Same-game stacking drag" },
  { n: "09", title: "Ticket A", blurb: "Primary cushion core" },
  { n: "10", title: "Ticket B", blurb: "Different names, same floor" },
  { n: "11", title: "Ticket C", blurb: "Fortress — strongest legs" },
  { n: "12", title: "Final AIN", blurb: "Rank C → A; never backfill cuts" },
] as const;

export const PRIORITY =
  "accuracy → probability → cushion → role → script → price → payout";

/** YIS: Underdog Strategist index. Parlay floor ≥ 80; no unresolved P/Q. */
export function scoreYis(leg: LegInput): number {
  const cushionScore = Math.min(40, Math.max(0, leg.cushion * 10));
  const floorScore = Math.min(20, Math.max(0, (leg.l5Floor / Math.max(1, parseFloat(leg.line) || 1)) * 12));
  const missPenalty = Math.min(15, leg.misses * 4);
  const script = Math.min(15, leg.scriptFit);
  const role = Math.min(15, leg.roleClarity);
  const injuryPenalty = Math.min(12, leg.injuryRisk);
  const corrPenalty = Math.min(10, leg.correlationDrag);
  const raw =
    cushionScore +
    floorScore +
    script +
    role +
    20 -
    missPenalty -
    injuryPenalty -
    corrPenalty;
  const capped = Math.round(Math.max(0, Math.min(100, raw)));
  return leg.unresolvedFlag ? Math.min(capped, 79) : capped;
}

export function verdictFor(yis: number, unresolved: boolean): Verdict {
  if (unresolved || yis < 70) return "CUT";
  if (yis >= 80) return "KEEP";
  return "HOLD";
}

export function scoreLeg(leg: LegInput): ScoredLeg {
  const yis = scoreYis(leg);
  return { ...leg, yis, verdict: verdictFor(yis, leg.unresolvedFlag) };
}

export function uid(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}
