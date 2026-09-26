/** Create + optionally publish a promo. No human approve step. */
import crypto from "node:crypto";
import path from "node:path";
import { buildCaption } from "./caption.js";
import { config } from "./config.js";
import { InstagramPublisher } from "./instagram.js";
import { buildPromoCard, type PromoKind } from "./promo.js";
import { renderCard } from "./render.js";
import { validateDraftForPublish } from "./safety.js";
import { DraftStore } from "./store.js";
import type { MarketingDraft } from "./types.js";

export type PromoRequest = {
  kind?: PromoKind;
  sport?: string;
  publish?: boolean;
};

export type PromoResult = {
  draft: MarketingDraft;
  published: boolean;
};

export async function createPromo(
  store: DraftStore,
  generatedDirectory: string,
  instagram: InstagramPublisher,
  input: PromoRequest = {}
): Promise<PromoResult> {
  const card = buildPromoCard({ kind: input.kind, sport: input.sport });
  const caption = buildCaption(card);
  const reasons = validateDraftForPublish(card, caption);
  if (reasons.length) {
    const error = new Error(`Promo failed safety check: ${reasons.join("; ")}`);
    (error as Error & { reasons: string[] }).reasons = reasons;
    throw error;
  }

  const id = crypto.randomUUID();
  const imageFilename = `${id}.png`;
  await renderCard(card, generatedDirectory, imageFilename);
  const now = new Date().toISOString();
  let draft: MarketingDraft = {
    id,
    cardId: card.id,
    createdAt: now,
    updatedAt: now,
    status: "APPROVED",
    caption,
    imageFilename,
    blockReasons: [],
    approvedAt: now,
    card
  };
  draft = await store.save(draft);

  const wantPublish = input.publish === true;
  if (!wantPublish) return { draft, published: false };

  if (!config.instagramPublishEnabled) {
    const error = new Error(
      "IG_PUBLISH_ENABLED is false. Turn it on once after Meta credentials are set, then posts go out without re-verify."
    );
    (error as Error & { draft: MarketingDraft }).draft = draft;
    throw error;
  }

  const imageUrl = `${config.publicBaseUrl}/generated/${encodeURIComponent(draft.imageFilename)}`;
  const instagramMediaId = await instagram.publishImage(imageUrl, draft.caption);
  const publishedAt = new Date().toISOString();
  draft = await store.save({
    ...draft,
    status: "PUBLISHED",
    publishedAt,
    updatedAt: publishedAt,
    instagramMediaId
  });
  return { draft, published: true };
}

export function startPromoScheduler(
  store: DraftStore,
  generatedDirectory: string,
  instagram: InstagramPublisher
): void {
  const hours = config.promoAutoIntervalHours;
  if (!hours || hours <= 0) return;
  if (!config.instagramPublishEnabled) {
    console.warn(
      `[promo-scheduler] PROMO_AUTO_INTERVAL_HOURS=${hours} but IG_PUBLISH_ENABLED=false — scheduler idle until publish is on.`
    );
    return;
  }
  const ms = hours * 60 * 60 * 1000;
  console.log(`[promo-scheduler] Auto-posting a promo every ${hours}h. No per-post approval.`);
  const tick = async () => {
    try {
      const result = await createPromo(store, generatedDirectory, instagram, { publish: true });
      console.log(`[promo-scheduler] Published ${result.draft.id} → IG ${result.draft.instagramMediaId}`);
    } catch (error) {
      console.error("[promo-scheduler] Failed:", error instanceof Error ? error.message : error);
    }
  };
  // First run after one interval (not immediately on boot) so deploy restarts don't spam.
  setInterval(() => {
    void tick();
  }, ms);
}

export function generatedDir(root = process.cwd()): string {
  return path.join(root, "public", "generated");
}
