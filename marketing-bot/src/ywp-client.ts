import { marketingFeedSchema } from "./card-schema.js";
import type { MarketingCard } from "./types.js";

export class YwpClient {
  constructor(
    private readonly baseUrl: string,
    private readonly feedPath: string,
    private readonly token: string
  ) {}

  async approvedCards(): Promise<MarketingCard[]> {
    const headers: Record<string, string> = { accept: "application/json" };
    if (this.token) headers.authorization = `Bearer ${this.token}`;
    const response = await fetch(`${this.baseUrl}${this.feedPath}`, { headers, signal: AbortSignal.timeout(15_000) });
    if (!response.ok) throw new Error(`YWP OS feed returned HTTP ${response.status}.`);
    const parsed = marketingFeedSchema.parse(await response.json());
    return parsed.cards;
  }
}
