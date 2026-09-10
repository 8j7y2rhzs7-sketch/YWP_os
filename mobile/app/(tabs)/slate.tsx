import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { PlayerPortrait } from "@/components/PlayerPortrait";
import { BrandHeader } from "@/components/BrandHeader";
import { EngineStage } from "@/components/EngineStage";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { MotionReveal } from "@/components/MotionReveal";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { SportBallIcon } from "@/components/SportBallIcon";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAppData } from "@/context/AppDataContext";
import { useAuth } from "@/context/AuthContext";
import { sportLook } from "@/sportVisuals";
import { colors, fonts, radius, spacing, type } from "@/theme";
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

function orbitToneFor(
  loading: boolean,
  slate: SlateResponse | null,
): "idle" | "loading" | "verified" | "partial" | "danger" {
  if (loading) return "loading";
  if (!slate) return "idle";
  const readiness = slateReadiness(slate);
  if (readiness === "VERIFIED") return "verified";
  if (readiness === "PARTIAL") return "partial";
  if (readiness === "DEMO") return "danger";
  return "idle";
}

function orbitLabel(
  loading: boolean,
  slate: SlateResponse | null,
): string | undefined {
  if (loading) return "Verifying";
  if (!slate) return "Standby";
  const readiness = slateReadiness(slate);
  if (readiness === "VERIFIED") return "Verified";
  if (readiness === "PARTIAL") return "Partial";
  if (readiness === "DEMO") return "Demo";
  return readiness;
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
  const { saveAnalysis, saveSlate } = useAppData();
  const [sport, setSport] = useState<(typeof sports)[number]["key"]>("mlb");
  const [date, setDate] = useState(localDate());
  const [slate, setSlate] = useState<SlateResponse | null>(null);
  const [loadingSlate, setLoadingSlate] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [catalogByKey, setCatalogByKey] = useState<Record<string, SportCatalogItem>>({});
  const [catalogReady, setCatalogReady] = useState(false);
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
    } finally {
      setCatalogReady(true);
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
      saveSlate(response);
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
    if (!catalogReady) return;
    void loadSlate();
    // Wait for catalog so OOS sports skip paid Odds; do not re-fetch when catalog object identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sport, date, catalogReady]);

  const tone = orbitToneFor(loadingSlate || analyzing, slate);
  const look = sportLook(sport);

  return (
    <Screen sport={sport}>
      <BrandHeader title="FULL PROTOCOL RUN" subtitle="AIN • STRICT MODE • ALL ANGLES" compact sport={sport} />

      {/* Focal engine — shockwaves + radar track load / readiness */}
      <View style={styles.engineStage}>
        <MotionReveal
          replayKey={`${sport}-${tone}-${loadingSlate}-${analyzing}`}
          fromY={24}
        >
          <EngineStage
            size={200}
            tone={tone}
            label={orbitLabel(loadingSlate || analyzing, slate)}
            intensity="hero"
            calloutsActive={Boolean(slate) && !loadingSlate}
            callouts={[
              {
                id: "sport",
                label: sport.toUpperCase(),
                side: "left",
                top: 48,
              },
              {
                id: "state",
                label: orbitLabel(loadingSlate || analyzing, slate) ?? "STANDBY",
                side: "right",
                top: 72,
              },
              {
                id: "count",
                label: slate ? `${slate.candidates.length} RAW` : "0 RAW",
                side: "left",
                top: 128,
              },
              {
                id: "mode",
                label: analyzing ? "AIN" : "STRICT",
                side: "right",
                top: 148,
              },
            ]}
          />
        </MotionReveal>
        <MotionReveal delay={120} replayKey={`${sport}-${slate?.candidates.length ?? 0}`}>
          <Text style={styles.engineHeadline}>
            {analyzing
              ? "Running AIN + Strict Mode"
              : loadingSlate
                ? "Pulling live candidates"
                : slate
                  ? `${sport.toUpperCase()} slate · ${slate.candidates.length} candidates`
                  : "Select sport · load slate"}
          </Text>
        </MotionReveal>
        <MotionReveal delay={220} replayKey={`${sport}-${slate?.notice ?? "idle"}`}>
          <Text style={styles.engineSupport}>
            {slate?.notice
              ? slate.notice
              : "Quiet chassis. Verification first. No forced ticket."}
          </Text>
        </MotionReveal>
      </View>

      <MetalPanel tone="gold" accent={look.accent}>
        <Text style={type.eyebrow}>SELECT SPORT</Text>
        <View style={styles.sports}>
          {sports.map((item) => {
            const catalog = catalogByKey[item.key];
            const outOfSeason = catalog?.in_season === false;
            const itemLook = sportLook(item.key);
            const active = sport === item.key;
            return (
              <Pressable
                key={item.key}
                onPress={() => setSport(item.key)}
                style={[
                  styles.sport,
                  active && {
                    borderColor: itemLook.accent,
                    backgroundColor: itemLook.accentSoft,
                  },
                  outOfSeason && styles.sportOutOfSeason,
                ]}
              >
                <View style={[styles.sportStripe, { backgroundColor: itemLook.accent }]} />
                <SportBallIcon
                  icon={item.icon}
                  spinning={active && (loadingSlate || analyzing)}
                  size={28}
                />
                <Text
                  style={[
                    styles.sportLabel,
                    active && { color: itemLook.stripe },
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
            <MetalPanel
              key={candidate.candidate_id}
              style={styles.candidate}
              accent={sportLook(sport).accent}
              motionDelay={Math.min(index, 8) * 45}
            >
              <View style={styles.candidateTop}>
                <Text style={[styles.number, { backgroundColor: sportLook(sport).accent }]}>{index + 1}</Text>
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
  engineStage: {
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.sm,
  },
  engineHeadline: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: -0.35,
    textAlign: "center",
  },
  engineSupport: {
    ...type.caption,
    textAlign: "center",
    maxWidth: 360,
    color: colors.silver,
  },
  sports: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  sport: {
    flex: 1,
    minWidth: 96,
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.12)",
    borderRadius: radius.md,
    backgroundColor: "rgba(8,16,24,0.9)",
    overflow: "hidden",
    minHeight: 88,
  },
  sportStripe: {
    position: "absolute",
    left: 0,
    top: 10,
    bottom: 10,
    width: 3,
    borderRadius: 2,
    opacity: 0.9,
  },
  sportOutOfSeason: { opacity: 0.42 },
  sportLabel: {
    color: colors.silver,
    fontFamily: fonts.bodyBold,
    fontWeight: "700",
    fontSize: 12,
    letterSpacing: 0.3,
  },
  sportLabelOutOfSeason: { color: colors.muted },
  oosBadge: {
    color: colors.danger,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  prefetchNote: {
    ...type.caption,
    color: colors.muted,
    marginTop: spacing.sm,
  },
  noticeHeader: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  noticeTitle: {
    flex: 1,
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: -0.25,
  },
  candidate: { padding: spacing.lg },
  candidateTop: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  number: {
    width: 32,
    height: 32,
    borderRadius: 16,
    lineHeight: 32,
    textAlign: "center",
    color: colors.background,
    backgroundColor: colors.gold,
    fontFamily: fonts.displaySemi,
    fontWeight: "700",
    overflow: "hidden",
  },
  candidateCopy: { flex: 1, gap: 3 },
  selection: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 16,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
  odds: {
    color: colors.gold,
    fontFamily: fonts.displaySemi,
    fontSize: 16,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
  market: {
    color: colors.success,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.7,
    textTransform: "uppercase",
  },
  footer: { ...type.caption, textAlign: "center", padding: spacing.md },
  verificationWarning: {
    color: colors.danger,
    fontSize: 13,
    fontWeight: "700",
    marginTop: spacing.sm,
  },
});
