import type { MarketingCard } from "./types.js";
import { buildPromoCaption } from "./promo.js";

function legLabel(index: number, card: MarketingCard): string {
  const leg = card.legs[index];
  const details = [leg.selection, leg.market, leg.line, leg.price].filter(Boolean).join(" • ");
  return `${index + 1}. ${leg.event}\n${details}`;
}

export function buildCaption(card: MarketingCard): string {
  if (card.sourceVersion === "promo" || card.id.startsWith("promo-")) {
    return buildPromoCaption(card);
  }
  const asOf = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short"
  }).format(new Date(card.verifiedAsOf));

  const score = typeof card.ywpScore === "number" ? `\nYWP Score: ${card.ywpScore.toFixed(0)}/100` : "";
  const book = card.sportsbook ? ` • ${card.sportsbook}` : "";
  return [
    `YWP OS ${card.sport.toUpperCase()} DECISION CARD`,
    card.title,
    "",
    ...card.legs.map((_, index) => legLabel(index, card)),
    score,
    `Verified as of ${asOf}${book}. Odds, lineups, and availability can change.`,
    "21+ • Bet responsibly. Analysis is informational and does not guarantee results.",
    "",
    "#YWPOS #SportsAnalysis #BetResponsibly"
  ].join("\n");
}
