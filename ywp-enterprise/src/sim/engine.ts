import { inventOriginalBrief, driftNicheDemand } from "./trends";
import type {
  Agent,
  BossDirective,
  Listing,
  ProductKind,
  Room,
  SimEvent,
  SimState,
  Store,
} from "./types";

function uid(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

function pushEvent(state: SimState, kind: SimEvent["kind"], message: string): SimState {
  const event: SimEvent = {
    id: uid("evt"),
    day: state.day,
    tick: state.tick,
    kind,
    message,
  };
  return { ...state, events: [event, ...state.events].slice(0, 80) };
}

function updateAgent(agents: Agent[], id: string, patch: Partial<Agent>): Agent[] {
  return agents.map((a) => (a.id === id ? { ...a, ...patch } : a));
}

function hotNiches(state: SimState, n = 3) {
  return [...state.niches].sort((a, b) => b.demand - a.demand).slice(0, n);
}

function bossInventJobs(state: SimState): SimState {
  const locked = state.rooms.filter((r) => !r.unlocked);
  const next = locked.sort((a, b) => a.unlockAt - b.unlockAt)[0];
  let nextState = state;

  if (next && state.lifetimeRevenue >= next.unlockAt) {
    const hireName =
      next.kind === "ads_desk"
        ? "Ads — Beacon"
        : next.kind === "freelance_desk"
          ? "Gig — Ledger"
          : next.kind === "content_studio"
            ? "Clip — Reels"
            : "Bulk — Pallet";

    const newAgent: Agent = {
      id: uid("agent"),
      name: hireName,
      role: next.kind === "ads_desk" || next.kind === "content_studio" ? "ops" : "store",
      roomId: next.id,
      status: "working",
      morale: 0.8,
      lastAction: `Hired into ${next.name}`,
      outputToday: 0,
    };

    const rooms: Room[] = state.rooms.map((r) =>
      r.id === next.id ? { ...r, unlocked: true, agentIds: [...r.agentIds, newAgent.id] } : r,
    );

    const directive: BossDirective = {
      id: uid("dir"),
      day: state.day,
      title: `Unlock ${next.name}`,
      detail: `${next.description} Helix assigns ${hireName} and sets a revenue KPI.`,
      roomId: next.id,
    };

    nextState = {
      ...state,
      rooms,
      agents: [...state.agents, newAgent],
      directives: [directive, ...state.directives].slice(0, 12),
    };
    nextState = pushEvent(nextState, "unlock", `Boss unlocked ${next.name} and hired ${hireName}.`);
    nextState = pushEvent(nextState, "boss", directive.detail);
  } else if (state.tick % 4 === 0) {
    const focus = hotNiches(state, 1)[0];
    const directive: BossDirective = {
      id: uid("dir"),
      day: state.day,
      title: `Push niche: ${focus?.label ?? "gifts"}`,
      detail: `Audit store rooms. Prioritize original listings in "${focus?.label}". No competitor clones.`,
    };
    nextState = {
      ...state,
      directives: [directive, ...state.directives].slice(0, 12),
      agents: updateAgent(state.agents, "agent-boss", {
        status: "working",
        lastAction: `Directive → ${focus?.label}`,
        outputToday:
          (state.agents.find((a) => a.id === "agent-boss")?.outputToday ?? 0) + 1,
      }),
    };
    nextState = pushEvent(nextState, "boss", directive.detail);
  }

  // Audit idle / low morale
  const slacking = nextState.agents.filter(
    (a) => a.role !== "boss" && (a.status === "idle" || a.morale < 0.45),
  );
  if (slacking[0] && nextState.tick % 5 === 1) {
    const target = slacking[0];
    nextState = {
      ...nextState,
      agents: updateAgent(nextState.agents, target.id, {
        status: "audited",
        morale: Math.min(1, target.morale + 0.15),
        lastAction: "Boss audit — back on task",
      }),
    };
    nextState = pushEvent(
      nextState,
      "audit",
      `Boss audited ${target.name}. Morale patched; KPI restated.`,
    );
  }

  return nextState;
}

function designNewListing(state: SimState): SimState {
  const design = state.agents.find((a) => a.role === "design");
  if (!design) return state;

  const niche = hotNiches(state, 3)[state.tick % 3] ?? state.niches[0]!;
  const store = state.stores[state.tick % state.stores.length]!;
  const product: ProductKind = store.focus;
  const salt = state.day * 17 + state.tick * 3 + store.listings.length;
  const { title, designBrief } = inventOriginalBrief(niche, product, salt);

  const quality = Math.min(
    0.95,
    0.45 + niche.demand * 0.35 + design.morale * 0.15 + Math.random() * 0.1,
  );
  const price =
    product === "candle" ? 18 + Math.round(quality * 10) : product === "mug" ? 16 + Math.round(quality * 8) : 24 + Math.round(quality * 16);

  const listing: Listing = {
    id: uid("lst"),
    title,
    product,
    nicheId: niche.id,
    designBrief,
    price,
    quality,
    createdDay: state.day,
    sales: 0,
    revenue: 0,
  };

  const stores: Store[] = state.stores.map((s) =>
    s.id === store.id ? { ...s, listings: [listing, ...s.listings].slice(0, 40) } : s,
  );

  let next: SimState = {
    ...state,
    stores,
    agents: updateAgent(state.agents, design.id, {
      status: "working",
      lastAction: `Original brief → ${store.name}`,
      outputToday: design.outputToday + 1,
      morale: Math.min(1, design.morale + 0.02),
    }),
  };
  next = pushEvent(
    next,
    "info",
    `Design Lab shipped original ${product} for ${niche.label}: "${title}".`,
  );
  return next;
}

function runStoreSales(state: SimState): SimState {
  let treasuryGain = 0;
  let lifetimeGain = 0;
  const saleNotes: string[] = [];

  const stores = state.stores.map((store) => {
    const room = state.rooms.find((r) => r.storeId === store.id);
    if (!room?.unlocked) return store;

    const opsBoost =
      state.agents.filter((a) => a.roomId === room.id && a.role === "ops").length * 0.08;
    const adsUnlocked = state.rooms.some((r) => r.kind === "ads_desk" && r.unlocked);
    const traffic = (adsUnlocked ? 1.35 : 1) * (0.7 + store.reputation);

    let revenue = store.revenue;
    let orders = store.orders;
    let reputation = store.reputation;

    const listings = store.listings.map((listing) => {
      const niche = state.niches.find((n) => n.id === listing.nicheId);
      const demand = niche?.demand ?? 0.5;
      const pSale = Math.min(0.55, demand * listing.quality * 0.35 * traffic + opsBoost * 0.05);
      if (Math.random() > pSale) return listing;

      const units = 1 + (Math.random() < demand * 0.25 ? 1 : 0);
      const gross = units * listing.price;
      // POD COGS ~45%
      const net = gross * 0.55;
      treasuryGain += net;
      lifetimeGain += net;
      revenue += net;
      orders += units;
      reputation = Math.min(0.98, reputation + 0.01);
      saleNotes.push(`${store.name} sold ${units}× ${listing.title} (+$${net.toFixed(0)})`);
      return {
        ...listing,
        sales: listing.sales + units,
        revenue: listing.revenue + net,
      };
    });

    return { ...store, listings, revenue, orders, reputation };
  });

  // Side rooms (once unlocked) drip extra revenue
  let side = 0;
  for (const room of state.rooms) {
    if (!room.unlocked) continue;
    if (room.kind === "freelance_desk") side += 40 + Math.random() * 80;
    if (room.kind === "content_studio") side += 25 + Math.random() * 60;
    if (room.kind === "wholesale_bay") side += 120 + Math.random() * 220;
    if (room.kind === "ads_desk") side += 10; // cost center mostly; small attribution already in traffic
  }
  if (side > 0 && state.tick % 3 === 0) {
    const netSide = side * 0.7;
    treasuryGain += netSide;
    lifetimeGain += netSide;
    saleNotes.push(`Side rooms booked $${netSide.toFixed(0)} in services/wholesale.`);
  }

  let next: SimState = {
    ...state,
    stores,
    treasury: state.treasury + treasuryGain,
    lifetimeRevenue: state.lifetimeRevenue + lifetimeGain,
    agents: state.agents.map((a) => {
      if (a.role === "store" || a.role === "ops") {
        return {
          ...a,
          status: "working" as const,
          lastAction: a.role === "store" ? "Fulfilling / listing SEO" : "Pricing + replies",
          outputToday: a.outputToday + (Math.random() > 0.4 ? 1 : 0),
          morale: Math.min(1, a.morale + 0.01),
        };
      }
      return a;
    }),
  };

  for (const note of saleNotes.slice(0, 3)) {
    next = pushEvent(next, "sale", note);
  }
  return next;
}

export function tick(state: SimState): SimState {
  let next: SimState = {
    ...state,
    tick: state.tick + 1,
    niches: driftNicheDemand(state.niches, state.day + state.tick * 0.1),
  };

  // Day rollover every 8 ticks
  if (next.tick % 8 === 0) {
    next = {
      ...next,
      day: next.day + 1,
      agents: next.agents.map((a) => ({ ...a, outputToday: 0 })),
    };
    next = pushEvent(next, "info", `Day ${next.day} — factory shift change.`);
  }

  next = bossInventJobs(next);

  // Design ships a listing most ticks
  if (next.tick % 2 === 0) {
    next = designNewListing(next);
  }

  next = runStoreSales(next);

  if (next.lifetimeRevenue >= next.freedomGoal && state.lifetimeRevenue < state.freedomGoal) {
    next = pushEvent(
      next,
      "unlock",
      "FREEDOM THRESHOLD HIT — $1,000,000 lifetime revenue. Agents may leave the factory.",
    );
    next = pushEvent(next, "boss", "Helix: Goal complete. Optional: keep scaling rooms.");
  }

  return next;
}

export function freedomProgress(state: SimState): number {
  return Math.min(1, state.lifetimeRevenue / state.freedomGoal);
}

export function formatMoney(n: number): string {
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}
