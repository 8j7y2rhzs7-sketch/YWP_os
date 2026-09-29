import { describe, expect, it } from "vitest";
import { buildCaption } from "../src/caption.js";
import { validateCardForDraft, validateDraftForPublish } from "../src/safety.js";
import type { MarketingCard } from "../src/types.js";

function card(overrides: Partial<MarketingCard> = {}): MarketingCard {
  return {
    id: "card-1",
    sport: "MLB",
    title: "Official Two-Pick Card",
    status: "VERIFIED",
    publicationEligible: true,
    demo: false,
    sportsbook: "Hard Rock",
    eventStart: "2026-09-26T23:00:00-04:00",
    verifiedAsOf: "2026-09-26T08:00:00-04:00",
    expiresAt: "2026-09-26T22:45:00-04:00",
    ywpScore: 84,
    legs: [{ id: "leg-1", event: "Away at Home", selection: "Home", market: "Moneyline", price: "-135" }],
    ...overrides
  };
}

const now = new Date("2026-09-26T12:00:00-04:00");

describe("marketing safety", () => {
  it("accepts a current verified publication-eligible card", () => {
    expect(validateCardForDraft(card(), now)).toEqual([]);
  });

  it("blocks demo and expired cards", () => {
    const reasons = validateCardForDraft(card({ demo: true, status: "DEMO", expiresAt: "2026-09-25T12:00:00-04:00" }), now);
    expect(reasons.join(" ")).toMatch(/DEMO/);
    expect(reasons.join(" ")).toMatch(/expired/i);
  });

  it("blocks certainty language", () => {
    expect(validateCardForDraft(card({ title: "Guaranteed lock" }), now).join(" ")).toMatch(/certainty/i);
  });

  it("produces a compliant caption", () => {
    const current = card();
    const caption = buildCaption(current);
    expect(caption).toContain("21+");
    expect(caption).toMatch(/responsibly/i);
    expect(validateDraftForPublish(current, caption, now)).toEqual([]);
  });
});
