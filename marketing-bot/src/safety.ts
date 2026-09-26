import type { MarketingCard } from "./types.js";

const prohibitedClaims = [
  /\bguaranteed\b/i,
  /\bcan(?:not|'t) lose\b/i,
  /\bsure win\b/i,
  /\brisk[- ]?free\b/i,
  /\b100%\b/i,
  /\bfree money\b/i,
  /\block(?:s|ed)?\b/i
];

export function findProhibitedClaims(text: string): string[] {
  return prohibitedClaims.filter((pattern) => pattern.test(text)).map((pattern) => pattern.source);
}

export function validateCardForDraft(card: MarketingCard, now = new Date()): string[] {
  const reasons: string[] = [];
  const isPromo = card.sourceVersion === "promo" || card.id.startsWith("promo-");
  if (card.status !== "VERIFIED") reasons.push(`Card status is ${card.status}, not VERIFIED.`);
  if (!card.publicationEligible) reasons.push("YWP OS has not marked this card publication-eligible.");
  if (card.demo) reasons.push("Demo data cannot be marketed as a current card.");
  if (new Date(card.expiresAt).getTime() <= now.getTime()) reasons.push("The card is expired.");
  if (new Date(card.verifiedAsOf).getTime() > now.getTime() + 60_000) reasons.push("verifiedAsOf is in the future.");
  if (card.legs.length < 1 || card.legs.length > 5) reasons.push("Cards must contain one to five legs.");
  if (card.legs.some((leg) => !leg.event || !leg.selection || !leg.market)) reasons.push("A leg is missing event, selection, or market details.");

  const claimText = [card.title, ...card.legs.flatMap((leg) => [leg.event, leg.selection, leg.market])].join(" ");
  // Promo creatives are brand/process copy — still block "guaranteed" etc., but allow product terms.
  const claims = findProhibitedClaims(claimText).filter((source) => {
    if (isPromo && source.includes("lock")) return false;
    return true;
  });
  if (claims.length) reasons.push("The source card contains prohibited certainty language.");
  return reasons;
}

export function validateDraftForPublish(card: MarketingCard, caption: string, now = new Date()): string[] {
  const reasons = validateCardForDraft(card, now);
  if (findProhibitedClaims(caption).length) reasons.push("The caption contains prohibited certainty language.");
  if (!/21\+/.test(caption)) reasons.push("The caption is missing the 21+ notice.");
  if (!/responsibly/i.test(caption)) reasons.push("The caption is missing responsible-betting language.");
  return [...new Set(reasons)];
}
