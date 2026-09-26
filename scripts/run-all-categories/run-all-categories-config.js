/**
 * Run-all-categories prompt builders for sportsbook screenshot sweeps.
 *
 * Usage:
 *   import {
 *     makeRunAllCategoriesSystemPrompt,
 *     makeRunAllCategoriesRequest,
 *   } from "./run-all-categories-config.js";
 *
 *   const systemPrompt = makeRunAllCategoriesSystemPrompt();
 *   const request = makeRunAllCategoriesRequest({
 *     sport: "NFL",
 *     game: "Giants @ Rams",
 *     screenshots: uploadedImages,
 *     visibleMarkets: sportsbookMarkets,
 *   });
 */

/** @typedef {{ url?: string, base64?: string, mimeType?: string, label?: string }} ScreenshotInput */
/** @typedef {{ category?: string, market?: string, player?: string, selection?: string, line?: number|string|null, odds?: number|string|null, book?: string }} VisibleMarket */

const CATEGORY_MAP = {
  NFL: [
    "Pass yards / pass TDs / completions / attempts / INTs",
    "Rush yards / rush TDs / rush attempts",
    "Reception yards / receptions / receiving TDs",
    "Anytime TD / first TD / 2+ TDs",
    "Combo yards (pass+rush, rush+rec, pass+rush+rec)",
    "Kicking points / FGs / PATs",
    "Longest completion / longest rush / longest reception",
    "Team totals / 1H / 1Q side markets when visible",
  ],
  NCAAF: [
    "Pass / rush / receiving yards and TDs",
    "Receptions / anytime TD / first TD",
    "Combo yards and total TDs",
    "Kicking markets",
    "Longest play props",
    "1H / 1Q team markets when visible",
  ],
  NBA: [
    "Points / rebounds / assists / threes",
    "PRA / PR / RA / PA combos",
    "Steals / blocks / turnovers",
    "Double-double / triple-double",
    "Team totals / 1H when visible",
  ],
  WNBA: [
    "Points / rebounds / assists / threes",
    "PRA (pts+reb+ast)",
    "Steals / blocks when booked",
    "Team totals / spreads when visible beside props",
  ],
  MLB: [
    "Pitcher Ks / outs / hits allowed / ERs / walks",
    "Batter hits / runs / RBIs / HRs / total bases",
    "H+R+RBI / stolen bases / walks",
    "Team totals / run line when visible",
  ],
  NHL: [
    "Points / goals / assists / shots on goal",
    "Saves / goals against (goalie)",
    "Team totals when visible",
  ],
};

const DEFAULT_CATEGORIES = [
  "Every player prop row visible in the screenshots",
  "Game lines (ML / spread / total) if shown",
  "Period markets (1H / 1Q) if shown",
];

/**
 * System prompt: force a full-category sweep, not a cherry-pick of 2–3 props.
 * @param {{ sport?: string }} [opts]
 */
export function makeRunAllCategoriesSystemPrompt(opts = {}) {
  const sportHint = opts.sport ? ` Sport context preference: ${opts.sport}.` : "";
  return [
    "You are a sportsbook prop analyst running an ALL-CATEGORIES sweep.",
    "Your job is to extract and grade every actionable market visible in the screenshots and the provided market list — not a shortlist of favorites.",
    sportHint,
    "",
    "Rules:",
    "1. Cover every category relevant to the sport (pass/rush/rec for football; PTS/REB/AST/3PM/PRA for basketball; etc.).",
    "2. Do not invent lines or odds. If a category is missing from screenshots and visibleMarkets, mark it NOT_VISIBLE.",
    "3. Prefer Over/Yes sides only when the book shows both and density matters — still report Under when it is the clear value.",
    "4. Separate BOOK PRICE from YOUR PROJECTION. Never treat sportsbook implied probability as your model.",
    "5. Flag injuries / questionable tags / backups when the slip shows them.",
    "6. Output strict JSON only (no markdown fences) matching the schema in the user message.",
    "7. Rank PLAY / LEAN / PASS per leg with a short reason (form, role, line vs mean, juice).",
    "8. If screenshots conflict with visibleMarkets, trust the screenshot price and note the conflict.",
  ]
    .filter(Boolean)
    .join("\n");
}

/**
 * Build a multimodal chat request payload for an all-categories run.
 *
 * @param {{
 *   sport: string,
 *   game: string,
 *   screenshots?: ScreenshotInput[],
 *   visibleMarkets?: VisibleMarket[],
 *   model?: string,
 *   maxLegs?: number,
 * }} input
 */
export function makeRunAllCategoriesRequest(input) {
  const sport = String(input.sport || "").trim().toUpperCase() || "SPORT";
  const game = String(input.game || "").trim() || "Unknown game";
  const screenshots = Array.isArray(input.screenshots) ? input.screenshots : [];
  const visibleMarkets = Array.isArray(input.visibleMarkets)
    ? input.visibleMarkets
    : [];
  const maxLegs = Number.isFinite(input.maxLegs) ? Number(input.maxLegs) : 40;
  const categories = CATEGORY_MAP[sport] || DEFAULT_CATEGORIES;

  const marketDigest =
    visibleMarkets.length === 0
      ? "(none provided — rely on screenshots)"
      : visibleMarkets
          .slice(0, 400)
          .map((m, i) => {
            const bits = [
              m.category || m.market || "market",
              m.player || null,
              m.selection || null,
              m.line != null ? `line ${m.line}` : null,
              m.odds != null ? `odds ${m.odds}` : null,
              m.book || null,
            ].filter(Boolean);
            return `${i + 1}. ${bits.join(" | ")}`;
          })
          .join("\n");

  const userText = [
    `Sport: ${sport}`,
    `Game: ${game}`,
    `Max legs to return: ${maxLegs}`,
    "",
    "Categories to sweep (mark NOT_VISIBLE when absent):",
    ...categories.map((c) => `- ${c}`),
    "",
    "visibleMarkets digest:",
    marketDigest,
    "",
    "Return JSON with shape:",
    JSON.stringify(
      {
        sport,
        game,
        categories_covered: ["string"],
        categories_missing: ["string"],
        legs: [
          {
            category: "string",
            player: "string|null",
            market: "string",
            selection: "string",
            line: "number|null",
            book_odds: "number|null",
            projection: "number|null",
            edge: "number|null",
            decision: "PLAY|LEAN|PASS",
            confidence: 0.0,
            reason: "string",
            source: "screenshot|visibleMarkets|both",
          },
        ],
        conflicts: ["string"],
        notes: ["string"],
      },
      null,
      2
    ),
  ].join("\n");

  const content = [{ type: "text", text: userText }];
  for (const shot of screenshots) {
    const part = screenshotToContentPart(shot);
    if (part) content.push(part);
  }

  return {
    model: input.model || "gpt-4.1",
    temperature: 0.2,
    response_format: { type: "json_object" },
    messages: [
      { role: "system", content: makeRunAllCategoriesSystemPrompt({ sport }) },
      { role: "user", content },
    ],
    metadata: {
      sport,
      game,
      screenshot_count: screenshots.length,
      visible_market_count: visibleMarkets.length,
      categories,
    },
  };
}

/**
 * @param {ScreenshotInput} shot
 */
function screenshotToContentPart(shot) {
  if (!shot || typeof shot !== "object") return null;
  if (shot.url) {
    return {
      type: "image_url",
      image_url: { url: shot.url },
      ...(shot.label ? { detail: "high", name: shot.label } : { detail: "high" }),
    };
  }
  if (shot.base64) {
    const mime = shot.mimeType || "image/png";
    const dataUrl = shot.base64.startsWith("data:")
      ? shot.base64
      : `data:${mime};base64,${shot.base64}`;
    return {
      type: "image_url",
      image_url: { url: dataUrl },
      detail: "high",
    };
  }
  return null;
}

export function listCategoriesForSport(sport) {
  const key = String(sport || "").trim().toUpperCase();
  return CATEGORY_MAP[key] || [...DEFAULT_CATEGORIES];
}

export default {
  makeRunAllCategoriesSystemPrompt,
  makeRunAllCategoriesRequest,
  listCategoriesForSport,
};
