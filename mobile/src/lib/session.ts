import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY = "ywp.os.session.v1";
const MAX_AGE_MS = 8 * 60 * 60 * 1000;

export type RunPhase = "idle" | "loading" | "warming" | "armed" | "analyzing";

export type SessionSnapshot = {
  pathname: string;
  sport: string | null;
  date: string | null;
  phase: RunPhase;
  savedAt: number;
};

let memory: SessionSnapshot | null = null;

function blank(): SessionSnapshot {
  return {
    pathname: "/",
    sport: null,
    date: null,
    phase: "idle",
    savedAt: Date.now(),
  };
}

export function rememberSession(partial: Partial<SessionSnapshot>) {
  const base = memory ?? blank();
  memory = {
    pathname: partial.pathname ?? base.pathname,
    sport: partial.sport === undefined ? base.sport : partial.sport,
    date: partial.date === undefined ? base.date : partial.date,
    phase: partial.phase ?? base.phase,
    savedAt: Date.now(),
  };
  AsyncStorage.setItem(KEY, JSON.stringify(memory)).catch(() => undefined);
}

export async function loadSession(): Promise<SessionSnapshot | null> {
  if (!memory) {
    try {
      const raw = await AsyncStorage.getItem(KEY);
      if (raw) memory = JSON.parse(raw) as SessionSnapshot;
    } catch {
      memory = null;
    }
  }
  if (!memory) return null;
  if (Date.now() - memory.savedAt > MAX_AGE_MS) return null;
  return memory;
}
