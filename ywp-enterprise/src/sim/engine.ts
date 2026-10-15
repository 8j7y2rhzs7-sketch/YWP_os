import { inventOriginalBrief, driftNicheDemand } from "./trends";
import { VENTURE_DECK, offerTitle } from "./ventures";
import type {
  Agent,
  BossDirective,
  BossIdea,
  Listing,
  ProductKind,
  Room,
  SimEvent,
  SimState,
  Store,
  VentureOffer,
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
  return { ...state, events: [event, ...state.events].slice(0, 100) };
}

function updateAgent(agents: Agent[], id: string, patch: Partial<Agent>): Agent[] {
  return agents.map((a) => (a.id === id ? { ...a, ...patch } : a));
}

function hotNiches(state: SimState, n = 3) {
  return [...state.niches].sort((a, b) => b.demand - a.demand).slice(0, n);
}

function blueprintForRoom(room: Room) {
  return VENTURE_DECK.find((v) => v.id === room.ventureId || v.kind === room.kind);
}

/** Boss queues the next idea before unlock, then staffs the room at threshold. */
function bossInventJobs(state: SimState): SimState {
  let nextState = state;
  const locked = state.rooms
    .filter((r) => !r.unlocked && r.ventureId)
    .sort((a, b) => a.unlockAt - b.unlockAt);
  const next = locked[0];

  // Preview / queue next idea so the floor sees Helix thinking beyond Etsy
  if (next && state.tick % 3 === 0) {
    const bp = blueprintForRoom(next);
    const already = state.ideas.some((i) => i.title.includes(next.name) && i.status !== "live");
    if (bp && !already && state.lifetimeRevenue < next.unlockAt) {
      const idea: BossIdea = {
        id: uid("idea"),
        day: state.day,
        channel: bp.channel,
        title: `Next build: ${bp.name}`,
        detail: `${bp.pitch} Unlocks at $${bp.unlockAt.toLocaleString()} lifetime.`,
        status: state.lifetimeRevenue >= bp.unlockAt * 0.7 ? "building" : "queued",
      };
      nextState = {
        ...nextState,
        ideas: [idea, ...nextState.ideas].slice(0, 16),
        agents: updateAgent(nextState.agents, "agent-boss", {
          lastAction: `Ideating ${bp.channel}`,
          status: "working",
          outputToday:
            (nextState.agents.find((a) => a.id === "agent-boss")?.outputToday ?? 0) + 1,
        }),
      };
      nextState = pushEvent(
        nextState,
        "boss",
        `Helix queued ${bp.channel}: "${bp.name}" — same playbook, new channel.`,
      );
    }
  }

  if (next && nextState.lifetimeRevenue >= next.unlockAt) {
    const bp = blueprintForRoom(next);
    const hireName = bp?.hireName ?? "Crew — Newhire";
    const hireRole = bp?.hireRole ?? "ops";

    const newAgent: Agent = {
      id: uid("agent"),
      name: hireName,
      role: hireRole,
      roomId: next.id,
      status: "working",
      morale: 0.82,
      lastAction: `Hired into ${next.name}`,
      outputToday: 0,
    };

    const rooms: Room[] = nextState.rooms.map((r) =>
      r.id === next.id ? { ...r, unlocked: true, agentIds: [...r.agentIds, newAgent.id] } : r,
    );

    const directive: BossDirective = {
      id: uid("dir"),
      day: nextState.day,
      title: `Go live: ${next.name}`,
      detail: `${next.description} Channel: ${next.channel}. Hire ${hireName}. KPI: first offers this shift.`,
      roomId: next.id,
    };

    const ideas = nextState.ideas.map((i) =>
      i.title.includes(next.name) ? { ...i, status: "live" as const } : i,
    );
    ideas.unshift({
      id: uid("idea"),
      day: nextState.day,
      channel: next.channel,
      title: `${next.name} is LIVE`,
      detail: directive.detail,
      status: "live",
    });

    nextState = {
      ...nextState,
      rooms,
      agents: [...nextState.agents, newAgent],
      directives: [directive, ...nextState.directives].slice(0, 14),
      ideas: ideas.slice(0, 16),
    };
    nextState = pushEvent(
      nextState,
      "unlock",
      `Boss opened ${next.name} on ${next.channel} and hired ${hireName}.`,
    );
    nextState = pushEvent(nextState, "boss", directive.detail);
  } else if (nextState.tick % 5 === 0) {
    const focus = hotNiches(nextState, 1)[0];
    const openChannels = [
      ...new Set(nextState.rooms.filter((r) => r.unlocked).map((r) => r.channel)),
    ].join(", ");
    const directive: BossDirective = {
      id: uid("dir"),
      day: nextState.day,
      title: `Push niche across channels: ${focus?.label ?? "gifts"}`,
      detail: `Live channels: ${openChannels}. Ship original offers only for "${focus?.label}".`,
    };
    nextState = {
      ...nextState,
      directives: [directive, ...nextState.directives].slice(0, 14),
      agents: updateAgent(nextState.agents, "agent-boss", {
        status: "working",
        lastAction: `Cross-channel → ${focus?.label}`,
        outputToday:
          (nextState.agents.find((a) => a.id === "agent-boss")?.outputToday ?? 0) + 1,
      }),
    };
    nextState = pushEvent(nextState, "boss", directive.detail);
  }

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
    product === "candle"
      ? 18 + Math.round(quality * 10)
      : product === "mug"
        ? 16 + Math.round(quality * 8)
        : 24 + Math.round(quality * 16);

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
      lastAction: `Original brief → ${store.channel}`,
      outputToday: design.outputToday + 1,
      morale: Math.min(1, design.morale + 0.02),
    }),
  };
  next = pushEvent(
    next,
    "info",
    `Design Lab → ${store.channel}: original ${product} for ${niche.label}: "${title}".`,
  );
  return next;
}

/** Non-POD rooms ship channel offers (gigs, downloads, clips…). */
function shipVentureOffers(state: SimState): SimState {
  const open = state.rooms.filter((r) => r.unlocked && r.ventureId);
  if (!open.length || state.tick % 2 !== 1) return state;

  const room = open[state.tick % open.length]!;
  const bp = blueprintForRoom(room);
  if (!bp) return state;

  const niche = hotNiches(state, 1)[0] ?? state.niches[0]!;
  const offer: VentureOffer = {
    id: uid("off"),
    roomId: room.id,
    title: offerTitle(bp, niche.label, state.day * 11 + state.tick),
    channel: room.channel,
    nicheId: niche.id,
    createdDay: state.day,
    sales: 0,
    revenue: 0,
  };

  const rooms = state.rooms.map((r) =>
    r.id === room.id ? { ...r, offers: [offer, ...r.offers].slice(0, 30) } : r,
  );

  const crew = state.agents.find((a) => a.roomId === room.id);
  let next: SimState = {
    ...state,
    rooms,
    agents: crew
      ? updateAgent(state.agents, crew.id, {
          status: "working",
          lastAction: `Shipped ${bp.offerLabel} on ${room.channel}`,
          outputToday: crew.outputToday + 1,
        })
      : state.agents,
  };
  next = pushEvent(
    next,
    "info",
    `${room.name} launched ${bp.offerLabel} on ${room.channel}: "${offer.title}".`,
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
    const contentBoost = state.rooms.some((r) => r.kind === "content_studio" && r.unlocked)
      ? 1.15
      : 1;
    const traffic = (adsUnlocked ? 1.35 : 1) * contentBoost * (0.7 + store.reputation);

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
      const net = gross * 0.55;
      treasuryGain += net;
      lifetimeGain += net;
      revenue += net;
      orders += units;
      reputation = Math.min(0.98, reputation + 0.01);
      saleNotes.push(
        `${store.channel} · ${store.name} sold ${units}× ${listing.title} (+$${net.toFixed(0)})`,
      );
      return {
        ...listing,
        sales: listing.sales + units,
        revenue: listing.revenue + net,
      };
    });

    return { ...store, listings, revenue, orders, reputation };
  });

  // Sync POD room revenue counters
  let rooms: Room[] = state.rooms.map((r) => {
    if (!r.storeId) return r;
    const store = stores.find((s) => s.id === r.storeId);
    return store ? { ...r, revenue: store.revenue } : r;
  });

  // Venture channel earnings
  rooms = rooms.map((room) => {
    if (!room.unlocked || !room.ventureId) return room;
    const bp = blueprintForRoom(room);
    if (!bp) return room;

    // Ads desk mainly boosts others; small direct earn
    const roll = bp.baseEarn + Math.random() * bp.earnSpread;
    const demand = hotNiches(state, 1)[0]?.demand ?? 0.6;
    const net = roll * (0.55 + demand * 0.5) * (state.tick % 3 === 0 ? 1 : 0.35);

    if (net < 1) return room;

    treasuryGain += net;
    lifetimeGain += net;

    let offers = room.offers;
    if (offers[0] && Math.random() > 0.4) {
      const top = offers[0];
      offers = [
        { ...top, sales: top.sales + 1, revenue: top.revenue + net },
        ...offers.slice(1),
      ];
      saleNotes.push(
        `${room.channel} · ${room.name} booked ${bp.offerLabel} (+$${net.toFixed(0)})`,
      );
    } else {
      saleNotes.push(`${room.channel} drip +$${net.toFixed(0)}`);
    }

    return { ...room, revenue: room.revenue + net, offers };
  });

  let next: SimState = {
    ...state,
    stores,
    rooms,
    treasury: state.treasury + treasuryGain,
    lifetimeRevenue: state.lifetimeRevenue + lifetimeGain,
    agents: state.agents.map((a) => {
      if (a.role === "store" || a.role === "ops") {
        return {
          ...a,
          status: "working" as const,
          lastAction:
            a.role === "store" ? "Selling / fulfilling across channel" : "Ops + channel SEO",
          outputToday: a.outputToday + (Math.random() > 0.4 ? 1 : 0),
          morale: Math.min(1, a.morale + 0.01),
        };
      }
      return a;
    }),
  };

  for (const note of saleNotes.slice(0, 4)) {
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

  if (next.tick % 8 === 0) {
    next = {
      ...next,
      day: next.day + 1,
      agents: next.agents.map((a) => ({ ...a, outputToday: 0 })),
    };
    next = pushEvent(next, "info", `Day ${next.day} — factory shift change.`);
  }

  next = bossInventJobs(next);

  if (next.tick % 2 === 0) {
    next = designNewListing(next);
  }

  next = shipVentureOffers(next);
  next = runStoreSales(next);

  if (next.lifetimeRevenue >= next.freedomGoal && state.lifetimeRevenue < state.freedomGoal) {
    next = pushEvent(
      next,
      "unlock",
      "FREEDOM THRESHOLD HIT — $1,000,000 lifetime revenue. Agents may leave the factory.",
    );
    next = pushEvent(next, "boss", "Helix: Goal complete. Keep inventing channels or cash out.");
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
