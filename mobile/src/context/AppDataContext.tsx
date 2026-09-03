import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import type { AnalyzeResponse, BuildTicketResponse } from "@/types";

const ANALYSES_KEY = "ywp.os.analyses.v3";
const BUILDS_KEY = "ywp.os.builds.v3";
const MAX_CACHED = 20;

interface AppDataValue {
  analyses: Record<string, AnalyzeResponse>;
  builds: Record<string, BuildTicketResponse>;
  saveAnalysis: (analysis: AnalyzeResponse) => void;
  saveBuild: (analysisId: string, build: BuildTicketResponse) => void;
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

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [analyses, setAnalyses] = useState<Record<string, AnalyzeResponse>>({});
  const [builds, setBuilds] = useState<Record<string, BuildTicketResponse>>({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [rawA, rawB] = await Promise.all([
          AsyncStorage.getItem(ANALYSES_KEY),
          AsyncStorage.getItem(BUILDS_KEY),
        ]);
        if (rawA) setAnalyses(JSON.parse(rawA));
        if (rawB) setBuilds(JSON.parse(rawB));
      } catch {
        /* first launch or corrupt data — start fresh */
      }
      setReady(true);
    })();
  }, []);

  const saveAnalysis = useCallback((analysis: AnalyzeResponse) => {
    setAnalyses((current) => {
      const next = trimToRecent(
        { ...current, [analysis.analysis_id]: analysis },
        MAX_CACHED,
      );
      AsyncStorage.setItem(ANALYSES_KEY, JSON.stringify(next)).catch(() => {});
      return next;
    });
  }, []);

  const saveBuild = useCallback(
    (analysisId: string, build: BuildTicketResponse) => {
      setBuilds((current) => {
        const next = trimToRecent(
          { ...current, [analysisId]: build },
          MAX_CACHED,
        );
        AsyncStorage.setItem(BUILDS_KEY, JSON.stringify(next)).catch(() => {});
        return next;
      });
    },
    [],
  );

  const value = useMemo(
    () => ({ analyses, builds, saveAnalysis, saveBuild, ready }),
    [analyses, builds, saveAnalysis, saveBuild, ready],
  );
  return (
    <AppDataContext.Provider value={value}>
      {children}
    </AppDataContext.Provider>
  );
}

export function useAppData(): AppDataValue {
  const value = useContext(AppDataContext);
  if (!value) throw new Error("useAppData must be used inside AppDataProvider");
  return value;
}
