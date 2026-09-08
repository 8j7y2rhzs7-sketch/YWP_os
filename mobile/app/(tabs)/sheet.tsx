import { router } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAppData } from "@/context/AppDataContext";
import { useAuth } from "@/context/AuthContext";
import { colors, radius, spacing, type } from "@/theme";
import type {
  AnalyzeResponse,
  CandidateInput,
  Recommendation,
  Ticket,
  TicketCard,
  SlateResponse,
} from "@/types";

function oddsLabel(odds: number): string {
  return odds > 0 ? `+${odds}` : String(odds);
}

function marketOrder(market: string): number {
  const key = market.toLowerCase();
  if (key.includes("moneyline") || key === "h2h") return 0;
  if (key.includes("run_line") || key.includes("spread")) return 1;
  if (key.includes("total_over") || key === "over") return 2;
  if (key.includes("total_under") || key === "under") return 3;
  if (key.includes("strikeout") || key.includes("prop")) return 4;
  return 5;
}

function groupByEvent(candidates: CandidateInput[]) {
  const map = new Map<string, CandidateInput[]>();
  for (const candidate of candidates) {
    const key = candidate.event_id || candidate.event_name;
    const list = map.get(key) ?? [];
    list.push(candidate);
    map.set(key, list);
  }
  return [...map.entries()].map(([eventId, items]) => ({
    eventId,
    eventName: items[0]?.event_name ?? eventId,
    startTime: String(items[0]?.start_time ?? ""),
    markets: [...items].sort(
      (a, b) =>
        marketOrder(a.market_type) - marketOrder(b.market_type) ||
        a.selection.localeCompare(b.selection),
    ),
  }));
}

export default function PickSheetScreen() {
  const { user, request } = useAuth();
  const { lastSlate, saveAnalysis, saveSlate, ready } = useAppData();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [stake, setStake] = useState("25");
  const [busy, setBusy] = useState(false);
  const [loadingSlate, setLoadingSlate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const slate = lastSlate;
  const games = useMemo(
    () => groupByEvent(slate?.candidates ?? []),
    [slate],
  );
  const selected = useMemo(
    () => (slate?.candidates ?? []).filter((item) => selectedIds.includes(item.candidate_id)),
    [slate, selectedIds],
  );

  function toggle(candidateId: string) {
    setSelectedIds((current) =>
      current.includes(candidateId)
        ? current.filter((id) => id !== candidateId)
        : [...current, candidateId],
    );
    setNote(null);
    setError(null);
  }

  async function refreshSlate() {
    if (!slate) {
      setError("Pull a slate on the Run tab first — this sheet reuses that same list.");
      return;
    }
    setLoadingSlate(true);
    setError(null);
    try {
      const response = await request<SlateResponse>(
        `/sports/slate?sport=${encodeURIComponent(slate.sport)}&date=${encodeURIComponent(slate.date)}`,
      );
      saveSlate(response);
      setSelectedIds([]);
      setNote(`Refreshed ${response.sport.toUpperCase()} ${response.date} — ${response.candidates.length} markets.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Slate refresh failed");
    } finally {
      setLoadingSlate(false);
    }
  }

  async function checkAndBuild() {
    if (!slate) {
      setError("No slate loaded. Open Run, refresh the raw slate, then come back here.");
      return;
    }
    if (!selected.length) {
      setError("Tap at least one market to build a ticket.");
      return;
    }
    const numericStake = Number(stake);
    if (!Number.isFinite(numericStake) || numericStake <= 0) {
      setError("Enter a stake greater than 0.");
      return;
    }
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const analysis = await request<AnalyzeResponse>("/sports/analyze", {
        method: "POST",
        body: JSON.stringify({
          sport: slate.sport,
          date: slate.date,
          mode: "pregame",
          user_risk_profile: user?.risk_profile ?? "balanced",
          candidates: slate.candidates,
        }),
      });
      saveAnalysis(analysis);

      const byCandidate = new Map<string, Recommendation>();
      for (const pick of [...analysis.ranked_picks, ...analysis.stay_away]) {
        byCandidate.set(pick.candidate_id, pick);
      }

      const cleared: Recommendation[] = [];
      const blocked: string[] = [];
      for (const leg of selected) {
        const pick = byCandidate.get(leg.candidate_id);
        if (pick && ["PLAY", "LEAN"].includes(pick.decision)) {
          cleared.push(pick);
        } else {
          const why = pick
            ? `${pick.decision}: ${pick.selection}`
            : `Missing after protocol: ${leg.selection}`;
          blocked.push(why);
        }
      }

      if (!cleared.length) {
        setError(
          blocked.length
            ? `Strict Mode blocked every selected leg. ${blocked.slice(0, 3).join(" · ")}`
            : "No selected markets cleared PLAY/LEAN.",
        );
        return;
      }

      const preview = await request<TicketCard>("/sports/preview-custom-card", {
        method: "POST",
        body: JSON.stringify({
          recommendation_ids: cleared.map((item) => item.id),
          label: `Custom ${cleared.length}-${cleared.length === 1 ? "leg" : "legs"}`,
        }),
      });

      const ticket = await request<Ticket>("/tickets", {
        method: "POST",
        body: JSON.stringify({
          ticket_type: "custom",
          label: preview.label,
          recommendation_ids: preview.recommendation_ids,
          stake: numericStake.toFixed(2),
          intentional_correlation: false,
          intentional_thesis_exposure: false,
          override_acknowledged: false,
        }),
      });

      if (blocked.length) {
        setNote(
          `${cleared.length} cleared, ${blocked.length} blocked by protocol. Opening Lock Check…`,
        );
      }
      router.push(`/ticket/${ticket.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ticket check failed");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) {
    return (
      <Screen>
        <LoadingState label="Loading pick sheet…" />
      </Screen>
    );
  }

  return (
    <Screen sport={slate?.sport}>
      <BrandHeader
        title="PICK SHEET"
        subtitle="SAME SLATE PULL • TAP MARKETS • CHECK LIKE APP TICKETS"
        compact
        sport={slate?.sport}
      />

      <MetalPanel tone="gold">
        <Text style={type.eyebrow}>SOURCE</Text>
        <Text style={styles.title}>
          {slate
            ? `${slate.sport.toUpperCase()} • ${slate.date}`
            : "No slate yet"}
        </Text>
        <Text style={type.body}>
          {slate
            ? `Reuses the Run tab pull (${slate.candidates.length} markets). Select sides, then protocol-check before Lock Check.`
            : "Open the Run tab, refresh a raw slate, then return here — no second Odds pull required."}
        </Text>
        <View style={styles.row}>
          <YwpButton
            label="REFRESH SAME SLATE"
            variant="outline"
            onPress={() => void refreshSlate()}
            loading={loadingSlate}
            disabled={!slate}
            style={styles.flex}
          />
          <YwpButton
            label="GO TO RUN"
            variant="outline"
            onPress={() => router.push("/(tabs)/slate")}
            style={styles.flex}
          />
        </View>
      </MetalPanel>

      {error ? <ErrorNotice message={error} /> : null}
      {note ? (
        <MetalPanel>
          <Text style={type.caption}>{note}</Text>
        </MetalPanel>
      ) : null}

      {slate ? (
        <>
          <SectionTitle
            title={`${games.length} Games`}
            subtitle="Tap a price to add or remove it from your slip."
          />
          {games.map((game) => (
            <MetalPanel key={game.eventId} style={styles.game}>
              <Text style={styles.gameTitle}>{game.eventName}</Text>
              {game.startTime ? (
                <Text style={type.caption}>{new Date(game.startTime).toLocaleString()}</Text>
              ) : null}
              <View style={styles.markets}>
                {game.markets.map((market) => {
                  const active = selectedIds.includes(market.candidate_id);
                  return (
                    <Pressable
                      key={market.candidate_id}
                      onPress={() => toggle(market.candidate_id)}
                      style={[styles.marketBtn, active && styles.marketBtnActive]}
                    >
                      <Text style={[styles.marketKind, active && styles.marketTextActive]}>
                        {market.market_type.replaceAll("_", " ").toUpperCase()}
                      </Text>
                      <Text style={[styles.marketPick, active && styles.marketTextActive]}>
                        {market.selection}
                      </Text>
                      <Text style={[styles.marketOdds, active && styles.marketTextActive]}>
                        {oddsLabel(market.american_odds)}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </MetalPanel>
          ))}

          <MetalPanel tone={selected.length ? "success" : "default"}>
            <View style={styles.slipHeader}>
              <Text style={styles.title}>Your slip</Text>
              <StatusPill value={`${selected.length} LEG${selected.length === 1 ? "" : "S"}`} />
            </View>
            {selected.length ? (
              selected.map((leg) => (
                <Text key={leg.candidate_id} style={type.body}>
                  • {leg.event_name} — {leg.selection} ({oddsLabel(leg.american_odds)})
                </Text>
              ))
            ) : (
              <Text style={type.caption}>No markets selected yet.</Text>
            )}
            <FormField
              label="STAKE ($)"
              value={stake}
              onChangeText={setStake}
              keyboardType="decimal-pad"
            />
            <YwpButton
              label={
                busy
                  ? "RUNNING PROTOCOL CHECK…"
                  : `CHECK ${Math.max(selected.length, 1)}-LEG TICKET`
              }
              onPress={() => void checkAndBuild()}
              loading={busy}
              disabled={!selected.length}
            />
            <Text style={type.caption}>
              Runs the same AIN / Strict Mode gates as official tickets, then opens Lock Check.
              Blocked legs stay off the ticket.
            </Text>
          </MetalPanel>
        </>
      ) : (
        <MetalPanel tone="danger">
          <StatusPill value="WAITING" />
          <Text style={styles.title}>Pull a slate on Run first</Text>
          <Text style={type.body}>
            This page does not spend a separate Odds call. It mirrors whatever the Run tab
            already loaded.
          </Text>
          <YwpButton label="OPEN RUN TAB" onPress={() => router.push("/(tabs)/slate")} />
        </MetalPanel>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: { color: colors.white, fontSize: 18, fontWeight: "900" },
  row: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  flex: { flex: 1 },
  game: { gap: spacing.sm },
  gameTitle: { color: colors.gold, fontWeight: "900", fontSize: 15 },
  markets: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  marketBtn: {
    minWidth: "47%",
    flexGrow: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
    backgroundColor: colors.backgroundRaised,
    gap: 2,
  },
  marketBtnActive: {
    borderColor: colors.gold,
    backgroundColor: colors.surfaceGold,
  },
  marketKind: { color: colors.muted, fontSize: 10, fontWeight: "800", letterSpacing: 0.6 },
  marketPick: { color: colors.white, fontWeight: "800", fontSize: 13 },
  marketOdds: { color: colors.gold, fontWeight: "900", fontSize: 16 },
  marketTextActive: { color: colors.background },
  slipHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
});
