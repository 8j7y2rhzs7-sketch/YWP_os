export type AgentRole = "boss" | "store" | "design" | "ops";

export type RoomKind =
  | "pod_store"
  | "design_lab"
  | "fulfillment"
  | "ads_desk"
  | "freelance_desk"
  | "content_studio"
  | "wholesale_bay";

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
  unlocked: boolean;
  unlockAt: number;
  description: string;
  agentIds: string[];
  storeId?: string;
}

export interface Store {
  id: string;
  name: string;
  focus: ProductKind;
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
  events: SimEvent[];
  compliance: {
    originalDesignsOnly: true;
    note: string;
  };
}
