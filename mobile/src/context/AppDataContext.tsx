import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

import type { AnalyzeResponse, BuildTicketResponse } from "@/types";

interface AppDataValue {
  analyses: Record<string, AnalyzeResponse>;
  builds: Record<string, BuildTicketResponse>;
  saveAnalysis: (analysis: AnalyzeResponse) => void;
  saveBuild: (analysisId: string, build: BuildTicketResponse) => void;
}

const AppDataContext = createContext<AppDataValue | null>(null);

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [analyses, setAnalyses] = useState<Record<string, AnalyzeResponse>>({});
  const [builds, setBuilds] = useState<Record<string, BuildTicketResponse>>({});

  const saveAnalysis = useCallback((analysis: AnalyzeResponse) => {
    setAnalyses((current) => ({ ...current, [analysis.analysis_id]: analysis }));
  }, []);
  const saveBuild = useCallback(
    (analysisId: string, build: BuildTicketResponse) => {
      setBuilds((current) => ({ ...current, [analysisId]: build }));
    },
    [],
  );
  const value = useMemo(
    () => ({ analyses, builds, saveAnalysis, saveBuild }),
    [analyses, builds, saveAnalysis, saveBuild],
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
