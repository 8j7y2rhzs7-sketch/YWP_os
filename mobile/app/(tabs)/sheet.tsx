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

const sports = [
  { key: "mlb", label: "MLB" },
  { key: "wnba", label: "WNBA" },
  { key: "nba", label: "NBA" },
  { key: "nfl", label: "NFL" },
  { key: "ncaaf", label: "NCAAF" },
  { key: "nhl", label: "NHL" },
  { key: "soccer", label: "SOCCER" },
  { key: "kbo", label: "KBO" },
] as const;

function localDate(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function oddsLabel(odds: number): string {
  return odds > 0 ? `+${odds}` : String(odds);
}

function marketOrder(market: string): number {
  const key = market.toLowerCase();
  if (key.includes("moneyline") || key === "h2h") return 0;
  if (key.includes("run_line") || key.includes("spread")) return 1;
  if (key.includes("total_over") || key === "over") return 2;
  if (key.includes("total_under") || key === "under") return 3;
  if (key.includes("strikeout") || key.includes("hits") || key.includes("prop")) return 4;
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
  const { lastMarketBoard, saveAnalysis, saveMarketBoard, ready } = useAppData();
  const [sport, setSport] = useState<(typeof sports)[number]["key"]>(
    (lastMarketBoard?.sport as (typeof sports)[number]["key"]) || "mlb",
  );
  const [date, setDate] = useState(lastMarketBoard?.date || localDate());
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [stake, setStake] = useState("25");
  const [busy, setBusy] = useState(false);
  const [loadingBoard, setLoadingBoard] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [grades, setGrades] = useState<Recommendation[]>([]);

  const board = lastMarketBoard;
  const games = useMemo(
    () => groupByEvent(board?.candidates ?? []),
    [board],
  );
  const selected = useMemo(
    () => (board?.candidates ?? []).filter((item) => selectedIds.includes(item.candidate_id)),
    [board, selectedIds],
  );
  const gradeByCandidate = useMemo(() => {
    const map = new Map<string, Recommendation>();
    for (const pick of grades) map.set(pick.candidate_id, pick);
    return map;
  }, [grades]);

  function toggle(candidateId: string) {
    setSelectedIds((current) =>
      current.includes(candidateId)
        ? current.filter((id) => id !== candidateId)
        : [...current, candidateId],
    );
    setNote(null);
    setError(null);
    setGrades([]);
  }

  async function loadBoard() {
    setLoadingBoard(true);
    setError(null);
    try {
      // Book menu first (fast). Model overlay is optional — it re-runs research and
      // was timing out / 503'ing the whole Sheet load on Render.
      const response = await request<SlateResponse>(
        `/sports/market-board?sport=${encodeURIComponent(sport)}&date=${encodeURIComponent(date)}&include_props=true&overlay_model=false`,
      );
      saveMarketBoard(response);
      setSelectedIds([]);
      setGrades([]);
      if (!response.candidates.length) {
        setNote(response.notice);
        setError(
          response.notice.includes("temporary error") || response.notice.includes("Could not fetch")
            ? response.notice
            : null,
        );
      } else {
        setNote(
          `Loaded ${response.candidates.length} sportsbook markets for ${response.sport.toUpperCase()} ${response.date}.`,
        );
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Market board failed");
    } finally {
      setLoadingBoard(false);
    }
  }

  async function checkAndBuild() {
    if (!board) {
      setError("Load the sportsbook menu first.");
      return;
    }
    if (!selected.length) {
      setError("Tap at least one market to grade.");
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
      // Grade only what the customer selected — full board can exceed analyze caps.
      const analysis = await request<AnalyzeResponse>("/sports/analyze", {
        method: "POST",
        body: JSON.stringify({
          sport: board.sport,
          date: board.date,
          mode: "pregame",
          user_risk_profile: user?.risk_profile ?? "balanced",
          candidates: selected,
        }),
      });
      saveAnalysis(analysis);

      const byCandidate = new Map<string, Recommendation>();
      for (const pick of [...analysis.ranked_picks, ...analysis.stay_away]) {
        byCandidate.set(pick.candidate_id, pick);
      }
      const orderedGrades = selected
        .map((leg) => byCandidate.get(leg.candidate_id))
        .filter((item): item is Recommendation => Boolean(item));
      setGrades(orderedGrades);

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

      setNote(
        `Graded ${orderedGrades.length} leg(s): ${cleared.length} PLAY/LEAN, ${blocked.length} blocked.`,
      );

      if (!cleared.length) {
        setError(
          blocked.length
            ? `Nothing cleared PLAY/LEAN — slip stays graded, ticket not built. ${blocked.slice(0, 3).join(" · ")}`
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
    <Screen sport={board?.sport || sport}>
      <BrandHeader
        title="PICK SHEET"
        subtitle="SPORTSBOOK MENU • SELECT ANY MARKET • YWP GRADES YOUR SLIP"
        compact
        sport={board?.sport || sport}
      />

      <MetalPanel tone="gold">
        <Text style={type.eyebrow}>BOARD</Text>
        <Text style={styles.title}>Hard Rock / DK style menu</Text>
        <Text style={type.body}>
          Pulls the full priced board (not just model-approved plays). Pick anything you want —
          Check grades each leg. Only PLAY/LEAN can become a ticket.
        </Text>
        <View style={styles.sportRow}>
          {sports.map((item) => {
            const active = sport === item.key;
            return (
              <Pressable
                key={item.key}
                onPress={() => setSport(item.key)}
                style={[styles.sportChip, active && styles.sportChipActive]}
              >
                <Text style={[styles.sportChipText, active && styles.sportChipTextActive]}>
                  {item.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <FormField label="DATE" value={date} onChangeText={setDate} />
        <YwpButton
          label={loadingBoard ? "LOADING BOARD…" : "LOAD SPORTSBOOK MENU"}
          onPress={() => void loadBoard()}
          loading={loadingBoard}
        />
        {board?.notice ? <Text style={type.caption}>{board.notice}</Text> : null}
      </MetalPanel>

      {error ? <ErrorNotice message={error} /> : null}
      {note ? (
        <MetalPanel>
          <Text style={type.caption}>{note}</Text>
        </MetalPanel>
      ) : null}

      {board ? (
        <>
          <SectionTitle
            title={`${games.length} Games · ${board.candidates.length} Markets`}
            subtitle="Tap prices like a sportsbook — hits, runs, RBIs, HRs, Ks, totals, and more. Model-backed markets can clear; book-only markets still show and grade."
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
                  const grade = gradeByCandidate.get(market.candidate_id);
                  return (
                    <Pressable
                      key={market.candidate_id}
                      onPress={() => toggle(market.candidate_id)}
                      style={[styles.marketBtn, active && styles.marketBtnActive]}
                    >
                      <Text style={[styles.marketKind, active && styles.marketTextActive]}>
                        {market.market_type.replaceAll("_", " ").toUpperCase()}
                        {market.probability_source === "model" ? " · MODEL" : " · BOOK"}
                      </Text>
                      <Text style={[styles.marketPick, active && styles.marketTextActive]}>
                        {market.selection}
                      </Text>
                      <Text style={[styles.marketOdds, active && styles.marketTextActive]}>
                        {oddsLabel(market.american_odds)}
                      </Text>
                      {grade ? (
                        <Text style={[styles.gradeTag, active && styles.marketTextActive]}>
                          {grade.decision}
                        </Text>
                      ) : null}
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
              selected.map((leg) => {
                const grade = gradeByCandidate.get(leg.candidate_id);
                return (
                  <Text key={leg.candidate_id} style={type.body}>
                    • {leg.event_name} — {leg.selection} ({oddsLabel(leg.american_odds)})
                    {grade ? ` → ${grade.decision}` : ""}
                  </Text>
                );
              })
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
                  ? "GRADING SLIP…"
                  : `GRADE ${Math.max(selected.length, 1)}-LEG SLIP`
              }
              onPress={() => void checkAndBuild()}
              loading={busy}
              disabled={!selected.length}
            />
            <Text style={type.caption}>
              Grades every selected market. PLAY/LEAN legs can build a ticket and open Lock Check.
              SKIP/REVIEW legs stay visible so you see why YWP would not approve them — that is the
              point of this sheet.
            </Text>
          </MetalPanel>
        </>
      ) : (
        <MetalPanel tone="danger">
          <StatusPill value="EMPTY" />
          <Text style={styles.title}>Load a sportsbook menu</Text>
          <Text style={type.body}>
            Sheet no longer mirrors only the Run raw pull. Load the full priced board here, then
            select and grade.
          </Text>
        </MetalPanel>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: { color: colors.white, fontSize: 18, fontWeight: "900" },
  sportRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginTop: spacing.sm },
  sportChip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    backgroundColor: colors.backgroundRaised,
  },
  sportChipActive: {
    borderColor: colors.gold,
    backgroundColor: colors.surfaceGold,
  },
  sportChipText: { color: colors.muted, fontWeight: "800", fontSize: 11 },
  sportChipTextActive: { color: colors.background },
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
  gradeTag: { color: colors.gold, fontSize: 11, fontWeight: "900", marginTop: 2 },
  marketTextActive: { color: colors.background },
  slipHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
});
