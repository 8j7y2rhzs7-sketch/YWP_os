import type { AgentRole, RoomKind } from "./types";

/** Any money machine the Boss can invent — not limited to Etsy. */
export interface VentureBlueprint {
  id: string;
  kind: RoomKind;
  name: string;
  channel: string;
  pitch: string;
  unlockAt: number;
  hireName: string;
  hireRole: AgentRole;
  /** Base net $ per qualifying tick once open */
  baseEarn: number;
  /** Extra variance */
  earnSpread: number;
  offerLabel: string;
}

/**
 * Boss idea deck. Same playbook as POD:
 * find demand → staff a room → ship original offers → scale.
 */
export const VENTURE_DECK: VentureBlueprint[] = [
  {
    id: "ads",
    kind: "ads_desk",
    name: "Room D — Paid Traffic Desk",
    channel: "Meta / TikTok Ads",
    pitch: "Buy attention for every storefront and gig room.",
    unlockAt: 2500,
    hireName: "Ads — Beacon",
    hireRole: "ops",
    baseEarn: 8,
    earnSpread: 20,
    offerLabel: "campaign",
  },
  {
    id: "fiverr",
    kind: "freelance_desk",
    name: "Room E — Freelance Bay (Fiverr/Upwork)",
    channel: "Fiverr / Upwork",
    pitch: "Sell listing audits, logo packs, and store SEO as gigs.",
    unlockAt: 8000,
    hireName: "Gig — Ledger",
    hireRole: "store",
    baseEarn: 55,
    earnSpread: 90,
    offerLabel: "gig",
  },
  {
    id: "shopify",
    kind: "shopify_store",
    name: "Room F — Shopify Flagship",
    channel: "Shopify",
    pitch: "Own-brand storefront for best-selling niches (not marketplace clones).",
    unlockAt: 18000,
    hireName: "Shop — Harbor",
    hireRole: "store",
    baseEarn: 70,
    earnSpread: 120,
    offerLabel: "SKU",
  },
  {
    id: "digital",
    kind: "digital_downloads",
    name: "Room G — Digital Downloads",
    channel: "Gumroad / Etsy Digital",
    pitch: "Planners, wall art files, and printables from original Design Lab work.",
    unlockAt: 28000,
    hireName: "Files — Pixel",
    hireRole: "ops",
    baseEarn: 45,
    earnSpread: 80,
    offerLabel: "download",
  },
  {
    id: "content",
    kind: "content_studio",
    name: "Room H — Content Studio",
    channel: "TikTok / Reels / Shorts",
    pitch: "Product clips + niche pages that feed every store and gig.",
    unlockAt: 40000,
    hireName: "Clip — Reels",
    hireRole: "ops",
    baseEarn: 35,
    earnSpread: 70,
    offerLabel: "clip pack",
  },
  {
    id: "affiliate",
    kind: "affiliate_desk",
    name: "Room I — Affiliate Desk",
    channel: "Amazon / brand affiliates",
    pitch: "Rank niche roundups and tool stacks; earn commissions on demand.",
    unlockAt: 55000,
    hireName: "Links — Relay",
    hireRole: "ops",
    baseEarn: 50,
    earnSpread: 100,
    offerLabel: "roundup",
  },
  {
    id: "merch",
    kind: "merch_marketplace",
    name: "Room J — Merch Marketplace",
    channel: "Amazon Merch / Redbubble",
    pitch: "Push original Design Lab art onto apparel marketplaces.",
    unlockAt: 75000,
    hireName: "Merch — Bolt",
    hireRole: "store",
    baseEarn: 60,
    earnSpread: 110,
    offerLabel: "tee/print",
  },
  {
    id: "newsletter",
    kind: "newsletter_desk",
    name: "Room K — Newsletter Desk",
    channel: "Substack / Beehiiv",
    pitch: "Own the audience; monetize with sponsors + product drops.",
    unlockAt: 95000,
    hireName: "Ink — Digest",
    hireRole: "ops",
    baseEarn: 40,
    earnSpread: 85,
    offerLabel: "issue",
  },
  {
    id: "youtube",
    kind: "youtube_studio",
    name: "Room L — YouTube Studio",
    channel: "YouTube",
    pitch: "Evergreen niche explainers that route traffic to shops and gigs.",
    unlockAt: 120000,
    hireName: "Tube — Frame",
    hireRole: "ops",
    baseEarn: 65,
    earnSpread: 130,
    offerLabel: "video",
  },
  {
    id: "wholesale",
    kind: "wholesale_bay",
    name: "Room M — Wholesale / Corporate Gifts",
    channel: "B2B wholesale",
    pitch: "Bulk gift sets for events and offices from proven niches.",
    unlockAt: 150000,
    hireName: "Bulk — Pallet",
    hireRole: "store",
    baseEarn: 140,
    earnSpread: 220,
    offerLabel: "bulk order",
  },
  {
    id: "saas",
    kind: "micro_saas",
    name: "Room N — Micro-SaaS Bay",
    channel: "SaaS (Stripe)",
    pitch: "Tiny paid tools (mockup batcher, listing title helper) for sellers.",
    unlockAt: 220000,
    hireName: "Code — Rivet",
    hireRole: "ops",
    baseEarn: 90,
    earnSpread: 160,
    offerLabel: "subscription",
  },
  {
    id: "leads",
    kind: "lead_gen",
    name: "Room O — Local Lead Gen",
    channel: "Google / local services",
    pitch: "Capture home-service leads and sell them to contractors.",
    unlockAt: 300000,
    hireName: "Leads — Catch",
    hireRole: "ops",
    baseEarn: 110,
    earnSpread: 180,
    offerLabel: "lead bundle",
  },
];

export function offerTitle(blueprint: VentureBlueprint, nicheLabel: string, salt: number): string {
  const hooks = [
    `${nicheLabel} starter pack`,
    `${nicheLabel} audit + fix`,
    `${nicheLabel} conversion kit`,
    `${nicheLabel} weekly drop`,
  ];
  return `${hooks[Math.abs(salt) % hooks.length]} — ${blueprint.offerLabel}`;
}
