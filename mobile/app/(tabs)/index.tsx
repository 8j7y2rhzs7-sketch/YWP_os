import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { DayForgeChamber } from "@/components/DayForgeChamber";
import { FrontDesk } from "@/components/FrontDesk";
import { LiveStrip } from "@/components/LiveStrip";
import { DayForgeReveal } from "@/components/DayForgeReveal";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { MotionReveal } from "@/components/MotionReveal";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { brand, colors, fonts, spacing, type } from "@/theme";
import type {
  Bankroll,
  DayForgeResponse,
  LearningPulse,
  Performance,
  ReadyBoard,
  Ticket,
} from "@/types";

function percent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function forgeRevealKey(forge: DayForgeResponse): string {
  const id = forge.play?.id ?? forge.analysis_id ?? forge.status;
  return `ywp.dayforge.revealed.${forge.date}.${forge.sport}.${id}`;
}

export default function CommandCenter() {
  const { user, request } = useAuth();
  const [bankroll, setBankroll] = useState<Bankroll | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [pulse, setPulse] = useState<LearningPulse | null>(null);
  const [forge, setForge] = useState<DayForgeResponse | null>(null);
  const [readyBoard, setReadyBoard] = useState<ReadyBoard | null>(null);
  const [revealOpen, setRevealOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastStatus = useRef<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const maybeAutoReveal = useCallback(async (next: DayForgeResponse) => {
    if (next.status !== "ready" && next.status !== "pass") return;
    const key = forgeRevealKey(next);
    try {
      const seen = await AsyncStorage.getItem(key);
      if (seen) return;
      await AsyncStorage.setItem(key, "1");
      setRevealOpen(true);
    } catch {
      setRevealOpen(true);
    }
  }, []);

  const loadForge = useCallback(async () => {
    try {
      const next = await request<DayForgeResponse>("/sports/day-forge");
      const previous = lastStatus.current;
      setForge(next);
      lastStatus.current = next.status;
      const flipped =
        previous === "cooking" && (next.status === "ready" || next.status === "pass");
      if (flipped || next.status === "ready" || next.status === "pass") {
        await maybeAutoReveal(next);
      }
    } catch {
      // Keep Home usable if forge is still warming / cold-starting.
    }
  }, [maybeAutoReveal, request]);

  const load = useCallback(
    async (refresh = false) => {
      refresh ? setRefreshing(true) : setLoading(true);
      setError(null);
      try {
        const [nextBankroll, nextTickets, nextPerformance, nextPulse] = await Promise.all([
          request<Bankroll>("/bankroll"),
          request<Ticket[]>("/tickets?limit=4"),
          request<Performance>("/learning/performance"),
          request<LearningPulse>("/learning/pulse"),
        ]);
        setBankroll(nextBankroll);
        setTickets(nextTickets);
        setPerformance(nextPerformance);
        setPulse(nextPulse);
        void loadForge();
        try {
          setReadyBoard(await request<ReadyBoard>("/sports/ready-board"));
        } catch {
          // Home still opens if the ready list is warming.
        }
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Dashboard failed to load");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [loadForge, request],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    // Keep polling while cooking OR soft stand-by (unavailable) so heat can
    // move once a live slate comes online — do not freeze at 5% forever.
    const shouldPoll =
      !forge || forge.status === "cooking" || forge.status === "unavailable";
    if (shouldPoll) {
      pollRef.current = setInterval(() => {
        void loadForge();
      }, 28_000);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [forge?.status, loadForge]);

  if (loading) {
    return (
      <Screen>
        <View style={styles.header}>
          <Text style={styles.kicker}>{brand.product}</Text>
          <LoadingState label="Getting today ready…" />
        </View>
      </Screen>
    );
  }

  const firstName = user?.name?.split(" ")[0] || "there";
  const support = pulse?.headline ?? "Pick a play, check the lock, then place it.";

  return (
    <Screen refreshing={refreshing} onRefresh={() => void load(true)}>
      <View style={styles.header}>
        <Text style={styles.kicker}>Today</Text>
        <Text style={styles.headerTitle}>{firstName}, start here.</Text>
        <Text style={styles.headerSupport} numberOfLines={2}>
          {support}
        </Text>
        <YwpButton label="Run today" onPress={() => router.push("/(tabs)/slate")} />
      </View>

      {error ? <ErrorNotice message={error} /> : null}

      <LiveStrip />

      <FrontDesk />

      <SectionTitle title="Ready plays" subtitle="Already waiting." />
      <MetalPanel>
        <View style={styles.protocolHeader}>
          <View style={styles.heroCopy}>
            <Text style={styles.panelTitle}>
              {readyBoard?.plays.length
                ? `${readyBoard.plays.length} approved play${readyBoard.plays.length === 1 ? "" : "s"}`
                : "Today's list"}
            </Text>
            <Text style={type.caption}>
              {readyBoard?.notice ?? "Checking matchups and the priced pull."}
            </Text>
          </View>
          <StatusPill value={(readyBoard?.status ?? "idle").replace(/_/g, " ").toUpperCase()} />
        </View>
        <YwpButton label="See plays" onPress={() => router.push("/ready")} />
      </MetalPanel>

      <SectionTitle title="Your numbers" />
      <MetalPanel>
        <View style={styles.metrics}>
          <Metric label="Bankroll" value={`$${Number(bankroll?.balance ?? 0).toFixed(2)}`} />
          <Metric
            label="Hit rate"
            value={percent(performance?.leg_win_rate ?? performance?.win_rate ?? null)}
            accent={colors.success}
          />
          <Metric
            label="P/L"
            value={`$${Number(performance?.profit_loss ?? 0).toFixed(2)}`}
            accent={Number(performance?.profit_loss ?? 0) >= 0 ? colors.success : colors.danger}
          />
        </View>
      </MetalPanel>

      <SectionTitle title="Tickets" subtitle="Still open." />
      {tickets.length ? (
        tickets.map((ticket) => (
          <MetalPanel key={ticket.id}>
            <View style={styles.ticketRow}>
              <View style={styles.heroCopy}>
                <Text style={styles.ticketTitle}>{ticket.label}</Text>
                <Text style={type.caption}>
                  {ticket.legs.length} legs • ${ticket.stake} • potential ${ticket.potential_payout}
                </Text>
              </View>
              <StatusPill value={ticket.last_lock_status ?? ticket.status} />
            </View>
            <YwpButton
              label="Open"
              variant="outline"
              onPress={() => router.push(`/ticket/${ticket.id}`)}
            />
          </MetalPanel>
        ))
      ) : (
        <MetalPanel>
          <Text style={styles.panelTitle}>Nothing open</Text>
          <Text style={type.body}>Save a card and it shows up here.</Text>
        </MetalPanel>
      )}

      <SectionTitle title="Day Forge" subtitle="One play when the data is ready." />
      <MotionReveal delay={80} fromY={24}>
        <DayForgeChamber
          forge={forge}
          onPress={() => {
            if (forge?.status === "ready" || forge?.status === "pass") {
              setRevealOpen(true);
            } else {
              void loadForge();
            }
          }}
        />
      </MotionReveal>

      <DayForgeReveal
        visible={revealOpen}
        forge={forge}
        onClose={() => setRevealOpen(false)}
        onRunProtocol={() => router.push("/(tabs)/slate")}
      />

    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    gap: spacing.md,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  kicker: {
    ...type.eyebrow,
    color: colors.muted,
  },
  headerTitle: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 34,
    fontWeight: "800",
    letterSpacing: -1,
    lineHeight: 38,
  },
  headerSupport: {
    ...type.body,
    color: colors.silver,
    maxWidth: 420,
  },
  heroCopy: { flex: 1, gap: spacing.sm },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  protocolHeader: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  panelTitle: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: -0.3,
  },
  ticketRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  ticketTitle: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: -0.25,
  },
});
