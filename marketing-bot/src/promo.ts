/** Brand / promo creatives — never real tickets or live odds. */
import crypto from "node:crypto";
import type { MarketingCard } from "./types.js";

export type PromoKind = "process" | "brand" | "sport_night" | "responsible";

type PromoTemplate = {
  kind: PromoKind;
  sport: string;
  title: string;
  scoreLabel: number;
  lines: Array<{ event: string; selection: string; market: string }>;
};

const TEMPLATES: PromoTemplate[] = [
  {
    kind: "process",
    sport: "MULTI",
    title: "Process Over Noise",
    scoreLabel: 88,
    lines: [
      { event: "Evidence first", selection: "Verified inputs only", market: "Protocol" },
      { event: "No vibes picks", selection: "Model + research gate", market: "Decision Engine" },
      { event: "Pre-entry check", selection: "Fresh price before entry", market: "Risk control" }
    ]
  },
  {
    kind: "brand",
    sport: "YWP OS",
    title: "Decision Support OS",
    scoreLabel: 90,
    lines: [
      { event: "Strict Mode", selection: "Incomplete research = no play", market: "Quality gate" },
      { event: "Hive learning", selection: "Settled outcomes only", market: "Calibration" },
      { event: "Bankroll rules", selection: "Caps before cards", market: "Discipline" }
    ]
  },
  {
    kind: "sport_night",
    sport: "MLB",
    title: "Slate Night Ritual",
    scoreLabel: 84,
    lines: [
      { event: "Scan the board", selection: "Universe before favorites", market: "Run" },
      { event: "Thin close", selection: "Pass when edge is fake", market: "Filter" },
      { event: "One cash band", selection: "Day Forge when ready", market: "Focus" }
    ]
  },
  {
    kind: "sport_night",
    sport: "NFL",
    title: "Sunday Process",
    scoreLabel: 86,
    lines: [
      { event: "Form + price", selection: "Independent probability", market: "Model" },
      { event: "Script check", selection: "Correlation guarded", market: "Ticket build" },
      { event: "Miss-by-1 review", selection: "Learn the near-misses", market: "Memory" }
    ]
  },
  {
    kind: "sport_night",
    sport: "WNBA",
    title: "Board Discipline",
    scoreLabel: 85,
    lines: [
      { event: "Props with research", selection: "No market-implied plays", market: "Strict Mode" },
      { event: "Availability", selection: "Injuries before entry", market: "Sweep" },
      { event: "Pass is a skill", selection: "SKIP protects the book", market: "Edge" }
    ]
  },
  {
    kind: "responsible",
    sport: "YWP OS",
    title: "Analysis ≠ Certainty",
    scoreLabel: 80,
    lines: [
      { event: "Informational only", selection: "No guaranteed outcomes", market: "Disclaimer" },
      { event: "21+ only", selection: "Bet responsibly", market: "Safety" },
      { event: "Lines move", selection: "Re-check before you play", market: "Freshness" }
    ]
  }
];

export function listPromoKinds(): PromoKind[] {
  return ["process", "brand", "sport_night", "responsible"];
}

export function buildPromoCard(input?: {
  kind?: PromoKind;
  sport?: string;
}): MarketingCard {
  const kind = input?.kind;
  const sportFilter = input?.sport?.trim().toUpperCase();
  let pool = TEMPLATES;
  if (kind) pool = pool.filter((t) => t.kind === kind);
  if (sportFilter) {
    const narrowed = pool.filter((t) => t.sport.toUpperCase() === sportFilter);
    if (narrowed.length) pool = narrowed;
  }
  const template = pool[Math.floor(Math.random() * pool.length)] ?? TEMPLATES[0];
  const now = new Date();
  const expires = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  return {
    id: `promo-${crypto.randomUUID()}`,
    sport: template.sport,
    title: template.title,
    status: "VERIFIED",
    publicationEligible: true,
    demo: false,
    sportsbook: null,
    eventStart: now.toISOString(),
    verifiedAsOf: now.toISOString(),
    expiresAt: expires.toISOString(),
    ywpScore: template.scoreLabel,
    modelProbability: null,
    dataQuality: "COMPLETE",
    sourceVersion: "promo",
    legs: template.lines.map((line, index) => ({
      id: `promo-leg-${index + 1}`,
      event: line.event,
      selection: line.selection,
      market: line.market,
      line: null,
      price: null
    }))
  };
}

export function buildPromoCaption(card: MarketingCard): string {
  const asOf = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    month: "short",
    day: "numeric",
    timeZoneName: "short"
  }).format(new Date(card.verifiedAsOf));

  return [
    `YWP OS — ${card.title}`,
    "",
    ...card.legs.map((leg, i) => `${i + 1}. ${leg.event}: ${leg.selection}`),
    "",
    "Marketing creative — not a live ticket, not betting advice.",
    `As of ${asOf}. 21+ • Bet responsibly. No outcome is assured.`,
    "",
    "#YWPOS #SportsAnalysis #ProcessOverNoise #BetResponsibly"
  ].join("\n");
}
