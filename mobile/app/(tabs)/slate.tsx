import { router } from "expo-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { AppState, Pressable, StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { EngineStage } from "@/components/EngineStage";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { MotionReveal } from "@/components/MotionReveal";
import { ProtocolRunDock } from "@/components/ProtocolRunDock";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { SportBallIcon } from "@/components/SportBallIcon";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useRunKeepAwake } from "@/components/StayAwake";
import { useAppData } from "@/context/AppDataContext";
import { useAuth } from "@/context/AuthContext";
import {
  ApiError,
  EDGE_CHALLENGE_MESSAGE,
  looksLikeEdgeChallenge,
} from "@/lib/api";
import { rememberSession, loadSession, type RunPhase } from "@/lib/session";
import { sportLook } from "@/sportVisuals";
import { colors, fonts, radius, spacing, type , registerStyles } from "@/theme";
import type {
  AnalyzeResponse,
  CandidateInput,
  OddsPrefetchResponse,
  PropWarmResponse,
  Readiness,
  SlateResponse,
  SportCatalogItem,
  SportsCatalogResponse,
} from "@/types";

const CANDIDATE_PAGE = 20;
const PROP_SPORTS = new Set(["wnba", "nba", "ncaab", "nfl", "ncaaf"]);
/** Chunked warm passes — each stays under Render's ~30s proxy. */
const MAX_WARM_ROUNDS = 14;
/** Giant boards need more slices than a normal slate. */
const MAX_WARM_ROUNDS_HUGE = 64;
/** Props shipped per warm request. Full boards time out without this. */
const WARM_CHUNK = 96;
const WARM_LONGSHOT_ODDS = 4000;
const WARM_LONGSHOT_CHUNK = 32;
/** Stop only after this many consecutive zero-gain passes. */
const STALL_ROUNDS_TO_ARM = 3;
/** Normal warm-request retries before arming with partial research. */
const WARM_RETRY_LIMIT = 3;
/** Extra retries when Cloudflare / edge rate-limits the burst. */
const WARM_EDGE_RETRY_LIMIT = 5;
/** Auto-continue a paused warm instead of making the user tap WARM again. */
const AUTO_RESUME_LIMIT = 4;

function isEdgeThrottleError(reason: unknown): boolean {
  if (!(reason instanceof Error)) return false;
  if (looksLikeEdgeChallenge(reason.message)) return true;
  if (reason.message.includes("Edge protection")) return true;
  if (!(reason instanceof ApiError)) return false;
  if (looksLikeEdgeChallenge(reason.details)) return true;
  return reason.status === 403 || reason.status === 429 || reason.status === 503;
}

function slateReadiness(slate: SlateResponse): Readiness {
  return slate.readiness ?? (slate.mode === "demo" ? "DEMO" : "PARTIAL");
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
  researchNote?: string | null,
): string | undefined {
  if (researchNote) return "Researching";
  if (loading) return "Verifying";
  if (!slate) return "Standby";
  const readiness = slateReadiness(slate);
  if (readiness === "VERIFIED") return "Verified";
  if (readiness === "PARTIAL") return "Partial";
  if (readiness === "DEMO") return "Demo";
  return readiness;
}

function pendingPropCount(candidates: CandidateInput[]): number {
  return candidates.filter(
    (row) =>
      String(row.market_type || "").startsWith("player_") &&
      row.probability_source === "market_implied",
  ).length;
}

function marketBreakdown(candidates: CandidateInput[]): Array<{ market: string; count: number }> {
  const counts = new Map<string, number>();
  for (const row of candidates) {
    const key = (row.market_type || "unknown").replaceAll("_", " ");
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([market, count]) => ({ market, count }))
    .sort((a, b) => b.count - a.count);
}

function CompactCandidateRow({
  candidate,
  index,
  accent,
}: {
  candidate: CandidateInput;
  index: number;
  accent: string;
}) {
  return (
    <View style={styles.denseRow}>
      <Text style={[styles.denseIndex, { color: accent }]}>{index + 1}</Text>
      <View style={styles.denseCopy}>
        <Text style={styles.denseSelection} numberOfLines={1}>
          {candidate.selection}
        </Text>
        <Text style={styles.denseMeta} numberOfLines={1}>
          {candidate.market_type.replaceAll("_", " ")} · {candidate.event_name}
        </Text>
      </View>
      <Text style={styles.denseOdds}>
        {candidate.american_odds > 0 ? "+" : ""}
        {candidate.american_odds}
      </Text>
    </View>
  );
}

const sports = [
  { key: "mlb", label: "MLB", icon: "⚾" },
  { key: "wnba", label: "WNBA", icon: "🏀" },
  { key: "nba", label: "NBA", icon: "🏀" },
  { key: "ncaab", label: "NCAAM", icon: "🏀" },
  { key: "nfl", label: "NFL", icon: "🏈" },
  { key: "ncaaf", label: "NCAAF", icon: "🏈" },
  { key: "nhl", label: "NHL", icon: "🏒" },
  { key: "soccer", label: "SOCCER", icon: "⚽" },
  { key: "tennis", label: "TENNIS", icon: "🎾" },
  { key: "kbo", label: "KBO", icon: "⚾" },
] as const;

type SportKey = (typeof sports)[number]["key"];

function isSportKey(value: string | null | undefined): value is SportKey {
  return sports.some((item) => item.key === value);
}

type LiveRun = {
  sport: SportKey;
  date: string;
  slate: SlateResponse | null;
  phase: RunPhase;
};

/** Same JS runtime: switching apps remounts the screen without dropping the board. */
let liveRun: LiveRun | null = null;

function localDate(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export default function SlateScreen() {
  const { user, request } = useAuth();
  const { saveAnalysis, saveSlate, lastSlate, ready: dataReady } = useAppData();
  const resumed = liveRun && liveRun.date === localDate() ? liveRun : null;
  const [gate, setGate] = useState(resumed != null);
  const [sport, setSport] = useState<SportKey>(resumed?.sport ?? "mlb");
  const [date, setDate] = useState(resumed?.date ?? localDate());
  const [slate, setSlate] = useState<SlateResponse | null>(resumed?.slate ?? null);
  const [loadingSlate, setLoadingSlate] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [researchNote, setResearchNote] = useState<string | null>(null);
  const [launchArmed, setLaunchArmed] = useState(resumed?.phase === "armed");
  const [warming, setWarming] = useState(resumed?.phase === "warming");
  const [error, setError] = useState<string | null>(null);
  const [catalogByKey, setCatalogByKey] = useState<Record<string, SportCatalogItem>>({});
  const [catalogReady, setCatalogReady] = useState(false);
  const [prefetchNote, setPrefetchNote] = useState<string | null>(null);
  const [prefetching, setPrefetching] = useState(false);
  const [visibleCount, setVisibleCount] = useState(CANDIDATE_PAGE);
  const warmEpoch = useRef(0);
  const heldSession = useRef<Awaited<ReturnType<typeof loadSession>>>(null);
  const launchWhenReady = useRef(false);
  const autoResumeCount = useRef(0);

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

  async function warmResearch(
    base: SlateResponse,
    epoch: number,
  ): Promise<SlateResponse | null> {
    const sportKey = base.sport.toLowerCase();
    if (!PROP_SPORTS.has(sportKey) || pendingPropCount(base.candidates) <= 0) {
      if (epoch === warmEpoch.current) {
        setLaunchArmed(true);
        setResearchNote(null);
        setWarming(false);
      }
      return base;
    }
    if (epoch === warmEpoch.current) {
      setLaunchArmed(false);
      setWarming(true);
    }
    let candidates = base.candidates;
    let latest = base;
    let stallRounds = 0;
    let errors = 0;
    const pendingStart = pendingPropCount(candidates);
    const roundCap =
      pendingStart > 400
        ? Math.min(
            MAX_WARM_ROUNDS_HUGE,
            Math.max(MAX_WARM_ROUNDS, Math.ceil(pendingStart / WARM_CHUNK) + 2),
          )
        : MAX_WARM_ROUNDS;
    try {
      for (let round = 0; round < roundCap; round += 1) {
        if (epoch !== warmEpoch.current) return null;
        const pendingBefore = pendingPropCount(candidates);
        if (pendingBefore <= 0) break;
        setResearchNote(
          `Researching props… pass ${round + 1}/${roundCap}`,
        );
        // Only ship a slice. A 4,000-row body never returns and the
        // button stays on WARM. Keep +4000-and-up in every slice.
        const pendingOnlyAll = candidates.filter(
          (row) =>
            String(row.market_type || "").startsWith("player_") &&
            row.probability_source === "market_implied",
        );
        const longshots = pendingOnlyAll.filter(
          (row) => Number(row.american_odds) >= WARM_LONGSHOT_ODDS,
        );
        const standard = pendingOnlyAll.filter(
          (row) => Number(row.american_odds) < WARM_LONGSHOT_ODDS,
        );
        const pendingOnly = [
          ...standard.slice(
            0,
            WARM_CHUNK - Math.min(longshots.length, WARM_LONGSHOT_CHUNK),
          ),
          ...longshots.slice(0, WARM_LONGSHOT_CHUNK),
        ];
        let warm: PropWarmResponse;
        try {
          warm = await request<PropWarmResponse>("/sports/warm-props", {
            method: "POST",
            body: JSON.stringify({
              sport: base.sport,
              date: base.date,
              candidates: pendingOnly,
              budget_seconds: 18,
            }),
          });
          errors = 0;
        } catch (reason) {
          errors += 1;
          if (epoch !== warmEpoch.current) return null;
          const edge = isEdgeThrottleError(reason);
          const limit = edge ? WARM_EDGE_RETRY_LIMIT : WARM_RETRY_LIMIT;
          const waitMs = edge ? Math.min(16_000, 4_000 * errors) : 1_500;
          const detail =
            edge
              ? EDGE_CHALLENGE_MESSAGE
              : reason instanceof Error && reason.message.trim()
                ? reason.message.trim()
                : "request failed";
          setResearchNote(
            `Research retry ${errors}/${limit} — ${detail}`,
          );
          if (errors >= limit) break;
          await new Promise((resolve) => setTimeout(resolve, waitMs));
          continue;
        }
        if (epoch !== warmEpoch.current) return null;
        const upgradedById = new Map(
          warm.candidates.map((row) => [row.candidate_id, row] as const),
        );
        candidates = candidates.map((row) => upgradedById.get(row.candidate_id) ?? row);
        latest = { ...base, candidates };
        setSlate(latest);
        saveSlate(latest);
        const pendingAfter = pendingPropCount(candidates);
        const modeled = candidates.filter(
          (row) =>
            String(row.market_type || "").startsWith("player_") &&
            (row.probability_source === "model" ||
              row.probability_source === "manual_verified"),
        ).length;
        const propTotal = candidates.filter((row) =>
          String(row.market_type || "").startsWith("player_"),
        ).length;
        const coverage =
          propTotal > 0 ? Math.round((modeled / propTotal) * 100) : 100;
        setResearchNote(`${modeled}/${propTotal} modeled (${coverage}%)`);
        if (pendingAfter <= 0 || coverage >= 92) {
          break;
        }
        if (warm.enriched_this_pass <= 0 && pendingAfter >= pendingBefore) {
          stallRounds += 1;
          setResearchNote(
            `${modeled}/${propTotal} modeled — stall ${stallRounds}/${STALL_ROUNDS_TO_ARM}`,
          );
          if (stallRounds >= STALL_ROUNDS_TO_ARM) break;
        } else {
          stallRounds = 0;
        }
        await new Promise((resolve) =>
          setTimeout(resolve, pendingStart > 400 ? 250 : 900),
        );
      }
      if (epoch === warmEpoch.current) {
        const stillPending = pendingPropCount(candidates);
        setLaunchArmed(true);
        setWarming(false);
        autoResumeCount.current = 0;
        setResearchNote(
          stillPending > 0
            ? launchWhenReady.current
              ? `Research armed — launching with ${stillPending} sportsbook-only props skipped.`
              : `Research armed — ${stillPending} props still sportsbook-only (will SKIP). Gold = grade.`
            : launchWhenReady.current
              ? "Research ready — launching."
              : "Research ready — LAUNCH is gold. Tap to grade.",
        );
      }
      return latest;
    } catch (reason) {
      if (epoch === warmEpoch.current) {
        setWarming(false);
        setLaunchArmed(false);
        const detail =
          reason instanceof Error && reason.message.trim()
            ? reason.message.trim()
            : "request failed";
        if (autoResumeCount.current < AUTO_RESUME_LIMIT) {
          autoResumeCount.current += 1;
          setResearchNote(
            `Research paused — auto-continuing ${autoResumeCount.current}/${AUTO_RESUME_LIMIT}. ${detail}`,
          );
          await new Promise((resolve) => setTimeout(resolve, 2_000));
          if (epoch !== warmEpoch.current) return latest;
          return warmResearch(latest, epoch);
        }
        setResearchNote(
          `Research paused — tap RUN once to continue. ${detail}`,
        );
      }
      return latest;
    }
  }

  async function loadSlate() {
    const requestSport = sport;
    const requestDate = date;
    const catalog = catalogByKey[requestSport];
    warmEpoch.current += 1;
    const epoch = warmEpoch.current;
    launchWhenReady.current = false;
    autoResumeCount.current = 0;
    setLaunchArmed(false);
    setWarming(false);
    setResearchNote(null);
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
      if (requestSport !== sport || requestDate !== date || epoch !== warmEpoch.current) {
        return;
      }
      setSlate(response);
      saveSlate(response);
      setLoadingSlate(false);
      // Auto-warm so gold LAUNCH means research finished — not a rushed grade.
      void warmResearch(response, epoch);
    } catch (reason) {
      if (requestSport !== sport || requestDate !== date) {
        return;
      }
      setSlate(null);
      const message =
        reason instanceof Error && reason.message.trim()
          ? reason.message.trim()
          : "Slate failed to load — check sign-in and retry REFRESH RAW SLATE.";
      setError(message);
      setLoadingSlate(false);
    }
  }

  async function gradeSlate(board: SlateResponse) {
    setAnalyzing(true);
    setError(null);
    setResearchNote("Grading with full research…");
    launchWhenReady.current = false;
    try {
      const response = await request<AnalyzeResponse>("/sports/analyze", {
        method: "POST",
        body: JSON.stringify({
          sport: board.sport,
          date: board.date,
          mode: "pregame",
          user_risk_profile: user?.risk_profile ?? "balanced",
          candidates: board.candidates,
        }),
      });
      saveAnalysis(response);
      router.push(`/analysis/${response.analysis_id}`);
    } catch (reason) {
      setError(
        reason instanceof Error && reason.message.trim()
          ? reason.message.trim()
          : "Analysis failed — reload the slate and try again.",
      );
    } finally {
      setAnalyzing(false);
      setResearchNote(null);
    }
  }

  async function analyze() {
    if (!slate) return;
    if (slate.sport.toLowerCase() !== sport || slate.date !== date) {
      setError("Slate is out of date — reload before analyzing.");
      return;
    }
    // One press during warm queues Launch — no need to keep tapping.
    if (warming) {
      launchWhenReady.current = true;
      setResearchNote("Queued — will launch when research turns gold.");
      return;
    }
    if (!launchArmed) {
      const epoch = warmEpoch.current;
      setError(null);
      launchWhenReady.current = true;
      setResearchNote("Continuing research — will launch when ready…");
      await warmResearch(slate, epoch);
      return;
    }
    await gradeSlate(slate);
  }

  const phase: RunPhase = analyzing
    ? "analyzing"
    : warming
      ? "warming"
      : loadingSlate
        ? "loading"
        : launchArmed
          ? "armed"
          : "idle";
  useRunKeepAwake(phase !== "idle" || Boolean(slate));

  useEffect(() => {
    if (!slate || !launchArmed || warming || analyzing || loadingSlate) return;
    if (!launchWhenReady.current) return;
    launchWhenReady.current = false;
    void gradeSlate(slate);
  }, [analyzing, launchArmed, loadingSlate, slate, warming]);

  useEffect(() => {
    void loadCatalog();
    if (resumed) return;
    void loadSession().then((session) => {
      heldSession.current = session;
      if (
        session &&
        session.date === localDate() &&
        isSportKey(session.sport)
      ) {
        setSport(session.sport);
        setDate(session.date);
      }
      setGate(true);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!gate) return;
    liveRun = { sport, date, slate, phase };
    rememberSession({ sport, date, phase });
  }, [gate, sport, date, slate, phase]);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state !== "background" || !slate) return;
      saveSlate(slate);
      rememberSession({ sport, date, phase });
    });
    return () => sub.remove();
  }, [date, phase, saveSlate, slate, sport]);

  const lastSlateRef = useRef(lastSlate);
  lastSlateRef.current = lastSlate;

  useEffect(() => {
    if (!catalogReady || !dataReady || !gate) return;
    let cancelled = false;
    void (async () => {
      const session = heldSession.current ?? (resumed ? await loadSession() : null);
      if (cancelled) return;
      const stored = lastSlateRef.current;
      const memoryBoard =
        liveRun &&
        liveRun.sport === sport &&
        liveRun.date === date &&
        liveRun.slate &&
        liveRun.slate.sport.toLowerCase() === sport &&
        liveRun.slate.date === date
          ? liveRun.slate
          : null;
      const storedBoard =
        stored && stored.sport.toLowerCase() === sport && stored.date === date
          ? stored
          : null;
      const board = memoryBoard ?? storedBoard;
      const sessionPhase =
        session && session.sport === sport && session.date === date ? session.phase : null;
      const recent =
        Boolean(memoryBoard) ||
        Boolean(session && Date.now() - session.savedAt < 8 * 60 * 60 * 1000);
      if (
        board &&
        recent &&
        (sessionPhase === "warming" ||
          sessionPhase === "armed" ||
          sessionPhase === "analyzing")
      ) {
        setSlate(board);
        setLoadingSlate(false);
        setVisibleCount(CANDIDATE_PAGE);
        if (sessionPhase === "warming" || liveRun?.phase === "warming") {
          warmEpoch.current += 1;
          setResearchNote("Picking the run back up…");
          void warmResearch(board, warmEpoch.current);
          return;
        }
        setLaunchArmed(true);
        setWarming(false);
        setResearchNote(
          sessionPhase === "analyzing"
            ? "Run was grading when you left. Tap LAUNCH to grade again."
            : "Back on this run.",
        );
        return;
      }
      setVisibleCount(CANDIDATE_PAGE);
      void loadSlate();
    })();
    return () => {
      cancelled = true;
    };
    // Resume a saved run instead of wiping the board. loadSlate/warmResearch close over the latest sport.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sport, date, catalogReady, dataReady, gate]);

  const tone = orbitToneFor(loadingSlate || analyzing || warming, slate);
  const look = sportLook(sport);
  const showRunDock = Boolean(slate && slate.candidates.length > 0);
  const markets = useMemo(
    () => (slate ? marketBreakdown(slate.candidates) : []),
    [slate],
  );
  const visibleCandidates = slate?.candidates.slice(0, visibleCount) ?? [];
  const hiddenCount = Math.max(0, (slate?.candidates.length ?? 0) - visibleCount);
  const engineLabel = orbitLabel(
    loadingSlate || analyzing || warming,
    slate,
    warming || researchNote ? researchNote ?? "Warming research" : null,
  );

  return (
    <View style={styles.page}>
    <Screen
      sport={sport}
      contentStyle={showRunDock ? styles.screenWithDock : undefined}
    >
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
            label={engineLabel}
            intensity="hero"
            calloutsActive={Boolean(slate) && !loadingSlate && !researchNote}
            callouts={[
              {
                id: "sport",
                label: sport.toUpperCase(),
                side: "left",
                top: 48,
              },
              {
                id: "state",
                label: engineLabel ?? "STANDBY",
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
                label: warming ? "RESEARCH" : analyzing ? "AIN" : "STRICT",
                side: "right",
                top: 148,
              },
            ]}
          />
        </MotionReveal>
        <MotionReveal delay={120} replayKey={`${sport}-${slate?.candidates.length ?? 0}-${researchNote ?? "idle"}`}>
          <Text style={styles.engineHeadline}>
            {warming || researchNote
              ? "Giving research time to finish"
              : analyzing
              ? "Running AIN + Strict Mode"
              : loadingSlate
                ? "Pulling live candidates"
                : slate
                  ? launchArmed
                    ? `${sport.toUpperCase()} ready · gold LAUNCH`
                    : `${sport.toUpperCase()} slate · ${slate.candidates.length} candidates`
                  : "Select sport · load slate"}
          </Text>
        </MotionReveal>
        <MotionReveal delay={220} replayKey={`${sport}-${slate?.notice ?? "idle"}-${researchNote ?? ""}`}>
          <Text style={styles.engineSupport}>
            {researchNote
              ? researchNote
              : slate?.notice
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
        <Text style={styles.prefetchNote}>
          Prop research on RUN uses free ESPN logs. You do not need to buy Odds credits for a normal Launch. This button only prefetches paid sportsbook odds across sports.
        </Text>
        <YwpButton
          label="WARM ALL IN-SEASON (USES CREDITS)"
          variant="outline"
          onPress={() => void warmInSeasonOdds()}
          loading={prefetching}
        />
        {prefetchNote ? <Text style={styles.prefetchNote}>{prefetchNote}</Text> : null}
      </MetalPanel>

      {error && error.trim() ? <ErrorNotice message={error} /> : null}
      {loadingSlate ? <LoadingState label="Verifying schedule and candidates…" /> : null}

      {slate ? (
        <>
          <MetalPanel tone={slateReadiness(slate) === "VERIFIED" ? "success" : "danger"}>
            <View style={styles.noticeHeader}>
              <Text style={styles.noticeTitle}>
                {slateReadiness(slate) === "VERIFIED"
                  ? "LIVE VERIFIED"
                  : slate.mode === "demo" || slateReadiness(slate) === "DEMO"
                    ? "DEMO DATA"
                    : slate.candidates.length === 0
                      ? sport === "kbo"
                        ? "LIVE — NO KBO EVENTS (TRY KOREA DATE)"
                        : "LIVE — NO EVENTS FOR THIS DATE"
                      : "LIVE — RESEARCH INCOMPLETE"}
              </Text>
              <StatusPill value={slateReadiness(slate) === "VERIFIED" ? "LOCKED" : "WARNING"} />
            </View>
            {slate.candidates.length === 0 && slate.mode !== "demo" ? (
              <Text style={styles.verificationWarning}>
                {sport === "kbo"
                  ? "KBO uses Korea (Asia/Seoul) calendar dates. If your phone is on a US date, step forward/back a day — empty is not demo mode."
                  : "No priced events for this date. This is a live empty board, not demo data."}
              </Text>
            ) : null}
            {slateReadiness(slate) === "PARTIAL" && slate.candidates.length > 0 ? (
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
            subtitle="Compressed view — use LAUNCH below. Expand only if you need to scan rows."
          />
          <MetalPanel tone="gold" accent={look.accent}>
            <View style={styles.noticeHeader}>
              <View style={styles.flexGrow}>
                <Text style={type.eyebrow}>SLATE HEAT</Text>
                <Text style={styles.noticeTitle}>
                  {slate.candidates.length.toLocaleString()} priced plays ready
                </Text>
              </View>
              <StatusPill value={`${slate.candidates.length}`} />
            </View>
            <Text style={type.body}>
              Protocol scores every candidate on LAUNCH — you do not need to scroll this list.
            </Text>
            <View style={styles.marketChips}>
              {markets.slice(0, 8).map((row) => (
                <View key={row.market} style={styles.marketChip}>
                  <Text style={styles.marketChipLabel}>{row.market}</Text>
                  <Text style={styles.marketChipCount}>{row.count}</Text>
                </View>
              ))}
              {markets.length > 8 ? (
                <Text style={type.caption}>+{markets.length - 8} more markets</Text>
              ) : null}
            </View>
          </MetalPanel>

          <MetalPanel accent={look.accent} style={styles.densePanel}>
            <Text style={type.eyebrow}>
              SHOWING {visibleCandidates.length} OF {slate.candidates.length}
            </Text>
            {visibleCandidates.map((candidate, index) => (
              <CompactCandidateRow
                key={candidate.candidate_id}
                candidate={candidate}
                index={index}
                accent={look.accent}
              />
            ))}
            {hiddenCount > 0 ? (
              <View style={styles.listActions}>
                <YwpButton
                  label={`SHOW ${Math.min(CANDIDATE_PAGE, hiddenCount)} MORE`}
                  variant="outline"
                  onPress={() =>
                    setVisibleCount((n) =>
                      Math.min(n + CANDIDATE_PAGE, slate.candidates.length),
                    )
                  }
                />
                {slate.candidates.length > CANDIDATE_PAGE * 2 ? (
                  <YwpButton
                    label={`SHOW ALL ${slate.candidates.length}`}
                    variant="outline"
                    onPress={() => setVisibleCount(slate.candidates.length)}
                  />
                ) : null}
              </View>
            ) : slate.candidates.length > CANDIDATE_PAGE ? (
              <YwpButton
                label="COLLAPSE LIST"
                variant="outline"
                onPress={() => setVisibleCount(CANDIDATE_PAGE)}
              />
            ) : null}
          </MetalPanel>

          <View style={styles.runFootnote}>
            <Text style={styles.footer}>
              Schedule • L5/L10 • matchup • script • line • cushion • role • injuries •
              motivation • variance • value • weakest leg • lock path
            </Text>
            <Text style={styles.dockHint}>
              Stylus LAUNCH stays pinned — tap it anytime. No need to scroll past {slate.candidates.length} plays.
            </Text>
          </View>
        </>
      ) : null}
    </Screen>
    {showRunDock ? (
      <ProtocolRunDock
        sport={sport}
        playCount={slate?.candidates.length ?? 0}
        readiness={slate ? slateReadiness(slate) : undefined}
        armed={launchArmed && !warming}
        loading={analyzing || warming}
        statusText={warming ? "WARM" : analyzing ? "RUN" : null}
        disabled={!slate?.candidates.length}
        onPress={() => void analyze()}
      />
    ) : null}
    </View>
  );
}

const styles = registerStyles(() => StyleSheet.create({
  page: { flex: 1 },
  screenWithDock: {
    // Clear tab bar + floating stylus RUN dock so the last plays stay readable.
    paddingBottom: 200,
  },
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
  flexGrow: { flex: 1 },
  densePanel: { paddingVertical: spacing.md, gap: 0 },
  denseRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "rgba(255,255,255,0.08)",
  },
  denseIndex: {
    width: 28,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
  },
  denseCopy: { flex: 1, gap: 1 },
  denseSelection: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 14,
    fontWeight: "700",
  },
  denseMeta: {
    ...type.caption,
    color: colors.muted,
  },
  denseOdds: {
    color: colors.gold,
    fontFamily: fonts.displaySemi,
    fontSize: 14,
    fontWeight: "700",
    minWidth: 48,
    textAlign: "right",
  },
  marketChips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  marketChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(240,193,74,0.35)",
    backgroundColor: "rgba(8,16,24,0.85)",
  },
  marketChipLabel: {
    color: colors.silver,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  marketChipCount: {
    color: colors.gold,
    fontFamily: fonts.displaySemi,
    fontSize: 13,
    fontWeight: "700",
  },
  listActions: { gap: spacing.sm, marginTop: spacing.md },
  footer: { ...type.caption, textAlign: "center", paddingHorizontal: spacing.md },
  runFootnote: { gap: spacing.sm, paddingBottom: spacing.md },
  dockHint: {
    ...type.caption,
    textAlign: "center",
    color: colors.gold,
    letterSpacing: 0.3,
  },
  verificationWarning: {
    color: colors.danger,
    fontSize: 13,
    fontWeight: "700",
    marginTop: spacing.sm,
  },
}));
