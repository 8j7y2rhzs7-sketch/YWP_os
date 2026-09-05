import { Platform } from "react-native";

import { rawRequest } from "@/lib/api";
import { getStoredTokens } from "@/lib/storage";

export type ErrorReportCategory =
  | "crash"
  | "api"
  | "pick_quality"
  | "ticket_build"
  | "ui"
  | "data"
  | "other";

export interface ErrorReportInput {
  category: ErrorReportCategory;
  message: string;
  screen?: string | null;
  stack?: string | null;
  analysisId?: string | null;
  recommendationId?: string | null;
  ticketId?: string | null;
  context?: Record<string, unknown>;
}

const APP_VERSION = "3.3.9";

export async function submitErrorReport(input: ErrorReportInput): Promise<void> {
  let accessToken: string | undefined;
  try {
    const raw = await getStoredTokens();
    if (raw) {
      const parsed = JSON.parse(raw) as { access_token?: string };
      accessToken = parsed.access_token;
    }
  } catch {
    accessToken = undefined;
  }

  await rawRequest(
    "/errors",
    {
      method: "POST",
      body: JSON.stringify({
        category: input.category,
        message: input.message,
        screen: input.screen ?? null,
        stack: input.stack ?? null,
        app_version: APP_VERSION,
        platform: Platform.OS,
        analysis_id: input.analysisId ?? null,
        recommendation_id: input.recommendationId ?? null,
        ticket_id: input.ticketId ?? null,
        context: input.context ?? {},
      }),
    },
    accessToken,
  );
}
