import path from "node:path";
import { renderCard } from "../src/render.js";
import type { MarketingCard } from "../src/types.js";

const preview: MarketingCard = {
  id: "preview-only",
  sport: "MLB",
  title: "Official Two-Pick Card",
  status: "VERIFIED",
  publicationEligible: true,
  demo: false,
  sportsbook: "Hard Rock",
  eventStart: "2026-09-26T19:10:00-04:00",
  verifiedAsOf: "2026-09-26T16:15:00-04:00",
  expiresAt: "2026-09-26T18:55:00-04:00",
  ywpScore: 84,
  legs: [
    { id: "preview-leg-1", event: "Away Team at Home Team", selection: "Home Team", market: "Moneyline", price: "-135" },
    { id: "preview-leg-2", event: "Visitor at Host", selection: "Over", market: "Game Total", line: "8.5" }
  ]
};

const directory = path.join(process.cwd(), "docs");
const result = await renderCard(preview, directory, "YWP_OS_Marketing_Bot_Preview.png");
console.log(result);
