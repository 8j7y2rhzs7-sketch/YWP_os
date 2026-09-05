import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { PlayerPortrait } from "@/components/PlayerPortrait";
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
  OddsPrefetchResponse,
  Readiness,
  SlateResponse,
  SportCatalogItem,
  SportsCatalogResponse,
} from "@/types";

function slateReadiness(slate: SlateResponse): Readiness {
  return slate.readiness ?? (slate.mode === "demo" ? "DEMO" : "PARTIAL");
}

function probabilityLabel(source: string | undefined): string {
  if (source === "market_implied") return "MARKET P";
  if (source === "demo") return "DEMO P";
  if (source === "manual_verified") return "VERIFIED P";
  return "MODEL P";
}

const sports = [
  { key: "mlb", label: "MLB", icon: "⚾" },
  { key: "wnba", label: "WNBA", icon: "🏀" },
  { key: "nba", label: "NBA", icon: "🏀" },
  { key: "nfl", label: "NFL", icon: "🏈" },
  { key: "ncaaf", label: "NCAAF", icon: "🏈" },
  { key: "nhl", label: "NHL", icon: "🏒" },
  { key: "soccer", label: "SOCCER", icon: "⚽" },
  { key: "kbo", label: "KBO", icon: "⚾" },
] as const;

function localDate(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export default function SlateScreen() {
  const { user, request } = useAuth();
  const { saveAnalysis } = useAppData();
  const [sport, setSport] = useState<(typeof sports)[number]["key"]>("mlb");
  const [date, setDate] = useState(localDate());
  const [slate, setSlate] = useState<SlateResponse | null>(null);
  const [loadingSlate, setLoadingSlate] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [catalogByKey, setCatalogByKey] = useState<Record<string, SportCatalogItem>>({});
  const [prefetchNote, setPrefetchNote] = useState<string | null>(null);
  const [prefetching, setPrefetching] = useState(false);

  async function loadCatalog() {
    try {
      const response = await request<SportsCatalogResponse>("/sports/catalog");
      const next: Record<string, SportCatalogItem> = {};
      for (const item of response.sports) {
        next[item.key] = item;
      }
      setCatalogByKey(next);
    } catch {
      // Catalog is advisory — slate still works without in-season badges.
    }
  }

  async function warmInSeasonOdds() {
    setPrefetching(true);
    setPrefetchNote(null);
    try {
      const response = await request<OddsPrefetchResponse>("/sports/prefetch-odds", {
        method: "POST",
        body: "{}",
      });
      setPrefetchNote(
        `Warmed ${response.warmed.length} sport(s), ${response.credits_spent} credits. ` +
          `Category switches reuse cache for ~${Math.round(response.cache_ttl_seconds / 60)} min.`,
      );
    } catch (reason) {
      setPrefetchNote(reason instanceof Error ? reason.message : "Prefetch failed");
    } finally {
      setPrefetching(false);
    }
  }

  async function loadSlate() {
    const requestSport = sport;
    const requestDate = date;
    const catalog = catalogByKey[requestSport];
    if (requestSport !== "mlb" && catalog?.in_season === false) {
      setSlate(null);
      setLoadingSlate(false);
      setError(
        `${catalog.label} is out of season — paid Odds refresh skipped. Pick an in-season sport.`,
      );
      return;
    }
    setLoadingSlate(true);
    setError(null);
    setSlate(null);
    try {
      const response = await request<SlateResponse>(
        `/sports/slate?sport=${encodeURIComponent(requestSport)}&date=${encodeURIComponent(requestDate)}`,
      );
      if (requestSport !== sport || requestDate !== date) {
        return;
      }
      setSlate(response);
    } catch (reason) {
      if (requestSport !== sport || requestDate !== date) {
        return;
      }
      setSlate(null);
      setError(reason instanceof Error ? reason.message : "Slate failed to load");
    } finally {
      if (requestSport === sport && requestDate === date) {
        setLoadingSlate(false);
      }
    }
  }

  async function analyze() {
    if (!slate) return;
    if (slate.sport.toLowerCase() !== sport || slate.date !== date) {
      setError("Slate is out of date — reload before analyzing.");
      return;
    }
    setAnalyzing(true);
    setError(null);
    try {
      const response = await request<AnalyzeResponse>("/sports/analyze", {
        method: "POST",
        body: JSON.stringify({
          sport: slate.sport,
          date: slate.date,
          mode: "pregame",
          user_risk_profile: user?.risk_profile ?? "balanced",
          candidates: slate.candidates,
        }),
      });
      saveAnalysis(response);
      router.push(`/analysis/${response.analysis_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  useEffect(() => {
    void loadCatalog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void loadSlate();
    // Reload whenever sport or date changes so analysis cannot use a stale slate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sport, date, catalogByKey]);

  return (
    <Screen sport={sport}>
      <BrandHeader title="FULL PROTOCOL RUN" subtitle="AIN • STRICT MODE • ALL ANGLES" compact sport={sport} />
      <MetalPanel tone="gold">
        <Text style={type.eyebrow}>SELECT SPORT</Text>
        <View style={styles.sports}>
          {sports.map((item) => {
            const catalog = catalogByKey[item.key];
            const outOfSeason = catalog?.in_season === false;
            return (
              <Pressable
                key={item.key}
                onPress={() => setSport(item.key)}
                style={[
                  styles.sport,
                  sport === item.key && styles.sportActive,
                  outOfSeason && styles.sportOutOfSeason,
                ]}
              >
                <Text style={styles.sportIcon}>{item.icon}</Text>
                <Text
                  style={[
                    styles.sportLabel,
                    sport === item.key && styles.sportLabelActive,
                    outOfSeason && styles.sportLabelOutOfSeason,
                  ]}
                >
                  {item.label}
                </Text>
                {outOfSeason ? <Text style={styles.oosBadge}>OOS</Text> : null}
              </Pressable>
            );
          })}
        </View>
        <FormField
          label="Slate date (YYYY-MM-DD)"
          value={date}
          onChangeText={setDate}
          autoCapitalize="none"
          keyboardType="numbers-and-punctuation"
        />
        <YwpButton
          label="REFRESH RAW SLATE"
          variant="outline"
          onPress={() => void loadSlate()}
          loading={loadingSlate}
        />
        <YwpButton
          label="WARM ALL IN-SEASON (USES CREDITS)"
          variant="outline"
          onPress={() => void warmInSeasonOdds()}
          loading={prefetching}
        />
        {prefetchNote ? <Text style={styles.prefetchNote}>{prefetchNote}</Text> : null}
      </MetalPanel>

      {error ? <ErrorNotice message={error} /> : null}
      {loadingSlate ? <LoadingState label="Verifying schedule and candidates…" /> : null}

      {slate ? (
        <>
          <MetalPanel tone={slateReadiness(slate) === "VERIFIED" ? "success" : "danger"}>
            <View style={styles.noticeHeader}>
              <Text style={styles.noticeTitle}>
                {slateReadiness(slate) === "VERIFIED"
                  ? "LIVE VERIFIED"
                  : slateReadiness(slate) === "PARTIAL"
                    ? "LIVE — RESEARCH INCOMPLETE"
                    : "DEMO DATA"}
              </Text>
              <StatusPill value={slateReadiness(slate) === "VERIFIED" ? "LOCKED" : "WARNING"} />
            </View>
            <Text style={type.body}>{slate.notice}</Text>
            {slateReadiness(slate) === "PARTIAL" ? (
              <Text style={styles.verificationWarning}>
                {slate.verification_summary?.partial_count ?? slate.candidates.length}{" "}
                candidate(s) are missing required verification. The engine will calculate
                them, but Strict Mode will return SKIP until every required input and an
                independent probability are supplied.
              </Text>
            ) : null}
          </MetalPanel>

          <SectionTitle
            title={`Raw ${sport.toUpperCase()} Candidate List`}
            subtitle="Raw list appears before YWP scoring, eliminations, and card building."
          />
          {slate.candidates.map((candidate, index) => (
            <MetalPanel key={candidate.candidate_id} style={styles.candidate}>
              <View style={styles.candidateTop}>
                <Text style={styles.number}>{index + 1}</Text>
                <PlayerPortrait
                  imageUrl={String(candidate.image_url ?? "") || null}
                  teamImageUrl={String(candidate.team_image_url ?? "") || null}
                  sport={sport}
                  size={46}
                />
                <View style={styles.candidateCopy}>
                  <Text style={styles.selection}>{candidate.selection}</Text>
                  <Text style={type.caption}>{candidate.event_name}</Text>
                </View>
                <Text style={styles.odds}>
                  {candidate.american_odds > 0 ? "+" : ""}
                  {candidate.american_odds}
                </Text>
              </View>
              <Text style={styles.market}>
                {candidate.market_type.replaceAll("_", " ")} •{" "}
                {probabilityLabel(candidate.probability_source)}{" "}
                {(candidate.estimated_probability * 100).toFixed(1)}% • DATA{" "}
                {(candidate.data_quality * 100).toFixed(0)}%
              </Text>
              <Text style={type.caption}>
                Probability source:{" "}
                {(candidate.probability_source ?? "model").replaceAll("_", " ")}
              </Text>
              {Array.isArray(candidate.source_urls) && candidate.source_urls[0] ? (
                <Pressable
                  accessibilityRole="link"
                  onPress={() => {
                    const sourceUrl = String(candidate.source_urls?.[0] ?? "");
                    if (sourceUrl) void Linking.openURL(sourceUrl);
                  }}
                  style={styles.sourceLink}
                >
                  <Text style={styles.sourceLinkText}>OPEN MLB SOURCE</Text>
                </Pressable>
              ) : null}
            </MetalPanel>
          ))}
          <YwpButton
            label="RUN AIN + STRICT MODE + MISS-BY-1"
            onPress={() => void analyze()}
            loading={analyzing}
            disabled={!slate.candidates.length}
          />
          <Text style={styles.footer}>
            Schedule • L5/L10 • matchup • script • line • cushion • role • injuries •
            motivation • variance • value • weakest leg • lock path
          </Text>
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  sports: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  sport: {
    flex: 1,
    minWidth: 92,
    alignItems: "center",
    gap: spacing.xs,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundRaised,
  },
  sportActive: { borderColor: colors.gold, backgroundColor: colors.surfaceGold },
  sportOutOfSeason: { opacity: 0.45 },
  sportIcon: { fontSize: 26 },
  sportLabel: { color: colors.muted, fontWeight: "900", fontSize: 11 },
  sportLabelActive: { color: colors.gold },
  sportLabelOutOfSeason: { color: colors.muted },
  oosBadge: {
    color: colors.danger,
    fontSize: 9,
    fontWeight: "900",
    letterSpacing: 0.6,
  },
  prefetchNote: {
    ...type.caption,
    color: colors.muted,
    marginTop: spacing.sm,
  },
  noticeHeader: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  noticeTitle: { flex: 1, color: colors.white, fontSize: 16, fontWeight: "900" },
  candidate: { padding: spacing.md },
  candidateTop: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  number: {
    width: 30,
    height: 30,
    borderRadius: 15,
    lineHeight: 30,
    textAlign: "center",
    color: colors.background,
    backgroundColor: colors.gold,
    fontWeight: "900",
  },
  candidateCopy: { flex: 1, gap: 2 },
  selection: { color: colors.white, fontSize: 16, fontWeight: "800" },
  odds: { color: colors.gold, fontSize: 16, fontWeight: "900" },
  market: {
    color: colors.success,
    fontSize: 10,
    fontWeight: "800",
    textTransform: "uppercase",
  },
  footer: { ...type.caption, textAlign: "center", padding: spacing.md },
  verificationWarning: {
    color: colors.danger,
    fontSize: 12,
    fontWeight: "800",
    marginTop: spacing.sm,
  },
  sourceLink: {
    alignSelf: "flex-start",
    borderColor: colors.info,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginTop: spacing.sm,
  },
  sourceLinkText: {
    color: colors.info,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0.8,
  },
});
