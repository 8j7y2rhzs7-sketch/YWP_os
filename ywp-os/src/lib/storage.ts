import type { PlacedResult, TicketState } from "./protocol";

const LEGS_KEY = "ywpos.legs.v1";
const TICKETS_KEY = "ywpos.tickets.v1";
const RESULTS_KEY = "ywpos.results.v1";

export function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function saveJson(key: string, value: unknown): void {
  localStorage.setItem(key, JSON.stringify(value));
}

export const storage = {
  legs: {
    key: LEGS_KEY,
    load: <T>(fb: T) => loadJson(LEGS_KEY, fb),
    save: (v: unknown) => saveJson(LEGS_KEY, v),
  },
  tickets: {
    key: TICKETS_KEY,
    load: (fb: TicketState) => loadJson(TICKETS_KEY, fb),
    save: (v: TicketState) => saveJson(TICKETS_KEY, v),
  },
  results: {
    key: RESULTS_KEY,
    load: () => loadJson<PlacedResult[]>(RESULTS_KEY, []),
    save: (v: PlacedResult[]) => saveJson(RESULTS_KEY, v),
  },
};
