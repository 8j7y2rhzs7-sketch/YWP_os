import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { getApiUrl } from "@/lib/api";
import type { AnalyzeResponse, BuildTicketResponse, SlateResponse } from "@/types";

const CACHE_SCHEMA = "v5";
const MAX_CACHED = 20;

interface AppDataValue {
  analyses: Record<string, AnalyzeResponse>;
  builds: Record<string, BuildTicketResponse>;
  lastSlate: SlateResponse | null;
  saveAnalysis: (analysis: AnalyzeResponse) => void;
  saveBuild: (analysisId: string, build: BuildTicketResponse) => void;
  saveSlate: (slate: SlateResponse) => void;
  clearCache: () => Promise<void>;
  ready: boolean;
}

const AppDataContext = createContext<AppDataValue | null>(null);

function trimToRecent<T>(record: Record<string, T>, max: number): Record<string, T> {
  const keys = Object.keys(record);
  if (keys.length <= max) return record;
  const trimmed: Record<string, T> = {};
  for (const key of keys.slice(-max)) {
    const val = record[key];
    if (val !== undefined) trimmed[key] = val;
  }
  return trimmed;
}

function scopeKey(kind: "analyses" | "builds" | "slate", userId: string | null): string {
  const api = getApiUrl().replace(/\/$/, "");
  const user = userId ?? "anonymous";
  return `ywp.os.${kind}.${CACHE_SCHEMA}.${user}.${api}`;
}

export function AppDataProvider({
  children,
  userId,
}: {
  children: ReactNode;
  userId: string | null;
}) {
  const [analyses, setAnalyses] = useState<Record<string, AnalyzeResponse>>({});
  const [builds, setBuilds] = useState<Record<string, BuildTicketResponse>>({});
  const [lastSlate, setLastSlate] = useState<SlateResponse | null>(null);
  const [ready, setReady] = useState(false);
  const hydrateGen = useRef(0);

  useEffect(() => {
    const gen = ++hydrateGen.current;
    setReady(false);
    setAnalyses({});
    setBuilds({});
    setLastSlate(null);
    void (async () => {
      try {
        const [rawA, rawB, rawS] = await Promise.all([
          AsyncStorage.getItem(scopeKey("analyses", userId)),
          AsyncStorage.getItem(scopeKey("builds", userId)),
          AsyncStorage.getItem(scopeKey("slate", userId)),
        ]);
        if (gen !== hydrateGen.current) return;
        if (rawA) setAnalyses(JSON.parse(rawA));
        if (rawB) setBuilds(JSON.parse(rawB));
        if (rawS) setLastSlate(JSON.parse(rawS));
      } catch {
        /* first launch or corrupt data — start fresh */
      }
      if (gen === hydrateGen.current) setReady(true);
    })();
  }, [userId]);

  const saveAnalysis = useCallback(
    (analysis: AnalyzeResponse) => {
      setAnalyses((current) => {
        const next = trimToRecent(
          { ...current, [analysis.analysis_id]: analysis },
          MAX_CACHED,
        );
        AsyncStorage.setItem(
          scopeKey("analyses", userId),
          JSON.stringify(next),
        ).catch(() => {});
        return next;
      });
    },
    [userId],
  );

  const saveBuild = useCallback(
    (analysisId: string, build: BuildTicketResponse) => {
      setBuilds((current) => {
        const next = trimToRecent(
          { ...current, [analysisId]: build },
          MAX_CACHED,
        );
        AsyncStorage.setItem(
          scopeKey("builds", userId),
          JSON.stringify(next),
        ).catch(() => {});
        return next;
      });
    },
    [userId],
  );

  const saveSlate = useCallback(
    (slate: SlateResponse) => {
      setLastSlate(slate);
      AsyncStorage.setItem(scopeKey("slate", userId), JSON.stringify(slate)).catch(
        () => {},
      );
    },
    [userId],
  );

  const clearCache = useCallback(async () => {
    hydrateGen.current += 1;
    setAnalyses({});
    setBuilds({});
    setLastSlate(null);
    await Promise.all([
      AsyncStorage.removeItem(scopeKey("analyses", userId)),
      AsyncStorage.removeItem(scopeKey("builds", userId)),
      AsyncStorage.removeItem(scopeKey("slate", userId)),
    ]).catch(() => undefined);
    setReady(true);
  }, [userId]);

  const value = useMemo(
    () => ({
      analyses,
      builds,
      lastSlate,
      saveAnalysis,
      saveBuild,
      saveSlate,
      clearCache,
      ready,
    }),
    [
      analyses,
      builds,
      lastSlate,
      saveAnalysis,
      saveBuild,
      saveSlate,
      clearCache,
      ready,
    ],
  );
  return (
    <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>
  );
}

export function useAppData(): AppDataValue {
  const value = useContext(AppDataContext);
  if (!value) throw new Error("useAppData must be used inside AppDataProvider");
  return value;
}
