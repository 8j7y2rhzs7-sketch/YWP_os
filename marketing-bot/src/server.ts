import crypto from "node:crypto";
import path from "node:path";
import express, { type NextFunction, type Request, type Response } from "express";
import { config } from "./config.js";
import { buildCaption } from "./caption.js";
import { dashboardHtml } from "./dashboard.js";
import { InstagramPublisher } from "./instagram.js";
import { renderCard } from "./render.js";
import { validateCardForDraft, validateDraftForPublish } from "./safety.js";
import { DraftStore } from "./store.js";
import type { MarketingDraft } from "./types.js";
import { YwpClient } from "./ywp-client.js";

const root = process.cwd();
const generatedDirectory = path.join(root, "public", "generated");
const store = new DraftStore(path.join(root, "data"));
const ywp = new YwpClient(config.ywpApiBaseUrl, config.ywpMarketingFeedPath, config.ywpApiToken);
const instagram = new InstagramPublisher(config.metaGraphVersion, config.instagramUserId, config.instagramAccessToken);
const app = express();

app.use(express.json({ limit: "1mb" }));
app.use("/generated", express.static(generatedDirectory, { immutable: false, maxAge: "5m" }));
app.get("/", (_request, response) => response.type("html").send(dashboardHtml));
app.get("/health", (_request, response) => response.json({ ok: true, service: "ywp-os-marketing-bot", publishEnabled: config.instagramPublishEnabled }));

function requireAdmin(request: Request, response: Response, next: NextFunction): void {
  const supplied = request.header("x-ywp-admin-key") ?? "";
  const expected = config.adminKey;
  const valid = supplied.length === expected.length && crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(expected));
  if (!valid) { response.status(401).json({ error: "Invalid admin key." }); return; }
  next();
}

app.use("/api", requireAdmin);

app.get("/api/drafts", async (_request, response, next) => {
  try { response.json({ drafts: await store.list(), publishEnabled: config.instagramPublishEnabled }); } catch (error) { next(error); }
});

app.post("/api/sync", async (_request, response, next) => {
  try {
    const cards = await ywp.approvedCards();
    let created = 0;
    let skipped = 0;
    for (const card of cards) {
      if (await store.findByCardId(card.id)) { skipped += 1; continue; }
      const now = new Date();
      const reasons = validateCardForDraft(card, now);
      const id = crypto.randomUUID();
      const imageFilename = `${id}.png`;
      await renderCard(card, generatedDirectory, imageFilename);
      const draft: MarketingDraft = {
        id,
        cardId: card.id,
        createdAt: now.toISOString(),
        updatedAt: now.toISOString(),
        status: reasons.length ? "BLOCKED" : "DRAFT",
        caption: buildCaption(card),
        imageFilename,
        blockReasons: reasons,
        card
      };
      await store.save(draft);
      created += 1;
    }
    response.json({ created, skipped });
  } catch (error) { next(error); }
});

app.post("/api/drafts/:id/approve", async (request, response, next) => {
  try {
    const draft = await store.get(request.params.id);
    if (!draft) { response.status(404).json({ error: "Draft not found." }); return; }
    const reasons = validateDraftForPublish(draft.card, draft.caption);
    if (reasons.length) { response.status(409).json({ error: "Draft failed safety review.", reasons }); return; }
    if (draft.status !== "DRAFT") { response.status(409).json({ error: `Draft is ${draft.status}, not DRAFT.` }); return; }
    const now = new Date().toISOString();
    const saved = await store.save({ ...draft, status: "APPROVED", approvedAt: now, updatedAt: now, blockReasons: [] });
    response.json({ draft: saved });
  } catch (error) { next(error); }
});

app.post("/api/drafts/:id/publish", async (request, response, next) => {
  try {
    if (!config.instagramPublishEnabled) { response.status(409).json({ error: "Instagram publishing is disabled. Set IG_PUBLISH_ENABLED=true only after Meta setup." }); return; }
    const draft = await store.get(request.params.id);
    if (!draft) { response.status(404).json({ error: "Draft not found." }); return; }
    if (draft.status !== "APPROVED") { response.status(409).json({ error: "Only an APPROVED draft can publish." }); return; }
    const reasons = validateDraftForPublish(draft.card, draft.caption);
    if (reasons.length) { response.status(409).json({ error: "Draft failed its final safety check.", reasons }); return; }
    const imageUrl = `${config.publicBaseUrl}/generated/${encodeURIComponent(draft.imageFilename)}`;
    const instagramMediaId = await instagram.publishImage(imageUrl, draft.caption);
    const now = new Date().toISOString();
    const saved = await store.save({ ...draft, status: "PUBLISHED", publishedAt: now, updatedAt: now, instagramMediaId });
    response.json({ draft: saved });
  } catch (error) { next(error); }
});

app.use((error: unknown, _request: Request, response: Response, _next: NextFunction) => {
  const message = error instanceof Error ? error.message : "Unknown error";
  console.error(error);
  response.status(500).json({ error: message });
});

if (process.env.NODE_ENV !== "test") {
  app.listen(config.port, () => console.log(`YWP OS Marketing Bot listening on port ${config.port}`));
}

export { app };
