import { describe, expect, it } from "vitest";
import { buildPromoCard, buildPromoCaption } from "../src/promo.js";
import { validateCardForDraft, validateDraftForPublish } from "../src/safety.js";

describe("promo creatives", () => {
  it("builds a postable marketing creative without live ticket fields", () => {
    const card = buildPromoCard({ kind: "process" });
    expect(card.id.startsWith("promo-")).toBe(true);
    expect(card.sourceVersion).toBe("promo");
    expect(card.legs.every((leg) => leg.price == null)).toBe(true);
    expect(validateCardForDraft(card)).toEqual([]);
    const caption = buildPromoCaption(card);
    expect(caption).toMatch(/not a live ticket/i);
    expect(validateDraftForPublish(card, caption)).toEqual([]);
  });
});
