/**
 * Example caller matching the product snippet.
 *
 *   import {
 *     makeRunAllCategoriesSystemPrompt,
 *     makeRunAllCategoriesRequest,
 *   } from "./run-all-categories-config.js";
 *
 * Provide `uploadedImages` and `sportsbookMarkets` from your upload / Odds flatten.
 */

import {
  makeRunAllCategoriesSystemPrompt,
  makeRunAllCategoriesRequest,
} from "./run-all-categories-config.js";

/** @type {import("./run-all-categories-config.js").ScreenshotInput[]} */
const uploadedImages = [];

/** @type {import("./run-all-categories-config.js").VisibleMarket[]} */
const sportsbookMarkets = [];

const systemPrompt = makeRunAllCategoriesSystemPrompt();

const request = makeRunAllCategoriesRequest({
  sport: "NFL",
  game: "Giants @ Rams",
  screenshots: uploadedImages,
  visibleMarkets: sportsbookMarkets,
});

export { systemPrompt, request };

if (import.meta.url === `file://${process.argv[1]}`) {
  console.log(
    JSON.stringify(
      {
        systemPromptChars: systemPrompt.length,
        model: request.model,
        categories: request.metadata.categories,
        messageRoles: request.messages.map((m) => m.role),
      },
      null,
      2
    )
  );
}
