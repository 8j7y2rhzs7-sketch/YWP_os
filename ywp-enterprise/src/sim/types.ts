export type AgentRole = "boss" | "store" | "design" | "ops";

export type RoomKind =
  | "pod_store"
  | "design_lab"
  | "fulfillment"
  | "ads_desk"
  | "freelance_desk"
  | "shopify_store"
  | "digital_downloads"
  | "content_studio"
  | "affiliate_desk"
  | "merch_marketplace"
  | "newsletter_desk"
  | "youtube_studio"
  | "wholesale_bay"
  | "micro_saas"
  | "lead_gen";

export type ProductKind = "mug" | "candle" | "personalized";

export interface TrendNiche {
  id: string;
  label: string;
  demand: number; // 0–1
  tags: string[];
}

export interface Listing {
  id: string;
  title: string;
  product: ProductKind;
  nicheId: string;
  /** Original prompt — never a scraped competitor design */
  designBrief: string;
  price: number;
  quality: number; // 0–1
  createdDay: number;
  sales: number;
  revenue: number;
}

/** Non-POD offer the Boss rooms ship (gigs, downloads, clips, etc.) */
export interface VentureOffer {
  id: string;
  roomId: string;
  title: string;
  channel: string;
  nicheId: string;
  createdDay: number;
  sales: number;
  revenue: number;
}

export interface Agent {
  id: string;
  name: string;
  role: AgentRole;
  roomId: string;
  status: "idle" | "working" | "blocked" | "audited";
  morale: number;
  lastAction: string;
  outputToday: number;
}

export interface Room {
  id: string;
  kind: RoomKind;
  name: string;
  channel: string;
  unlocked: boolean;
  unlockAt: number;
  description: string;
  agentIds: string[];
  storeId?: string;
  /** Set when Boss invents from the venture deck */
  ventureId?: string;
  revenue: number;
  offers: VentureOffer[];
}

export interface Store {
  id: string;
  name: string;
  focus: ProductKind;
  channel: string;
  listings: Listing[];
  revenue: number;
  orders: number;
  reputation: number;
}

export interface BossDirective {
  id: string;
  day: number;
  title: string;
  detail: string;
  roomId?: string;
}

export interface BossIdea {
  id: string;
  day: number;
  channel: string;
  title: string;
  detail: string;
  status: "queued" | "building" | "live";
}

export interface SimEvent {
  id: string;
  day: number;
  tick: number;
  kind: "info" | "sale" | "unlock" | "audit" | "warn" | "boss";
  message: string;
}

export interface SimState {
  day: number;
  tick: number;
  running: boolean;
  speedMs: number;
  treasury: number;
  lifetimeRevenue: number;
  freedomGoal: number;
  agents: Agent[];
  rooms: Room[];
  stores: Store[];
  niches: TrendNiche[];
  directives: BossDirective[];
  ideas: BossIdea[];
  events: SimEvent[];
  compliance: {
    originalDesignsOnly: true;
    note: string;
  };
}
