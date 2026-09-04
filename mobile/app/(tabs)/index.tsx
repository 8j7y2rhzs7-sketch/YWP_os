import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { brandAssets } from "@/brandAssets";
import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { brand, colors, fonts, spacing, type } from "@/theme";
import type {
  Bankroll,
  LearningPulse,
  Performance,
  ProtocolDefinition,
  Ticket,
} from "@/types";

function percent(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export default function CommandCenter() {
  const { user, request } = useAuth();
  const [bankroll, setBankroll] = useState<Bankroll | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [protocol, setProtocol] = useState<ProtocolDefinition | null>(null);
  const [pulse, setPulse] = useState<LearningPulse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (refresh = false) => {
      refresh ? setRefreshing(true) : setLoading(true);
      setError(null);
      try {
        const [nextBankroll, nextTickets, nextPerformance, nextProtocol, nextPulse] =
          await Promise.all([
            request<Bankroll>("/bankroll"),
            request<Ticket[]>("/tickets?limit=4"),
            request<Performance>("/learning/performance"),
            request<ProtocolDefinition>("/protocol/current"),
            request<LearningPulse>("/learning/pulse"),
          ]);
        setBankroll(nextBankroll);
        setTickets(nextTickets);
        setPerformance(nextPerformance);
        setProtocol(nextProtocol);
        setPulse(nextPulse);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Dashboard failed to load");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [request],
  );

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <Screen>
        <BrandHeader />
        <LoadingState label="Loading command center…" />
      </Screen>
    );
  }

  return (
    <Screen refreshing={refreshing} onRefresh={() => void load(true)}>
      <BrandHeader />
      <View style={styles.engineHero}>
        <Image
          source={brandAssets.decisionEngine}
          style={styles.engineArt}
          resizeMode="cover"
          accessibilityLabel="YWP Decision Engine brand artwork"
        />
        <View style={styles.engineScrim} />
        <View style={styles.engineCopy}>
          <Text style={styles.brandMark}>YWP OS</Text>
          <Text style={type.eyebrow}>WELCOME BACK, {user?.name}</Text>
          <Text style={styles.heroTitle}>It learns every time you use it.</Text>
        </View>
      </View>
      <MetalPanel tone="gold" style={styles.hero}>
        <View style={styles.heroTop}>
          <View style={styles.heroCopy}>
            <Text style={styles.heroText}>
              {pulse?.headline ??
                "Run a slate, lock a ticket, grade a result. Quiet metal is the chassis — edge is the point."}
            </Text>
          </View>
          <StatusPill value={protocol?.status ?? "canonical"} />
        </View>
        <View style={styles.metrics}>
          <Metric label="Bankroll" value={`$${Number(bankroll?.balance ?? 0).toFixed(2)}`} />
          <Metric
            label="Win rate"
            value={percent(performance?.win_rate ?? null)}
            accent={colors.success}
          />
          <Metric label="Settled" value={performance?.settled ?? 0} />
          <Metric label="Trained" value={pulse?.micro_updates ?? 0} accent={colors.gold} />
          <Metric
            label="P/L"
            value={`$${Number(performance?.profit_loss ?? 0).toFixed(2)}`}
            accent={
              Number(performance?.profit_loss ?? 0) >= 0
                ? colors.success
                : colors.danger
            }
          />
        </View>
        <YwpButton label="RUN TODAY'S FULL PROTOCOL" onPress={() => router.push("/(tabs)/slate")} />
      </MetalPanel>
      {error ? <ErrorNotice message={error} /> : null}

      <SectionTitle
        title="Protocol State"
        subtitle="Newest workflow is canonical; superseded rules stay removed."
      />
      <MetalPanel>
        <View style={styles.protocolHeader}>
          <View style={styles.heroCopy}>
            <Text style={styles.panelTitle}>{protocol?.name ?? "YWP OS Protocol"}</Text>
            <Text style={type.caption}>VERSION {protocol?.version ?? brand.protocolVersion}</Text>
          </View>
          <StatusPill value="DOUBLE_CLEARED" />
        </View>
        <Text style={styles.rule}>✓ AIN seven-angle sweep</Text>
        <Text style={styles.rule}>✓ Strict sport-specific verification</Text>
        <Text style={styles.rule}>✓ Vision and cushion grading</Text>
        <Text style={styles.rule}>✓ Miss-by-1 ticket-killer detection</Text>
        <Text style={styles.rule}>✓ Lock Check immediately before placement</Text>
        <Text style={styles.rule}>✓ Guarded self-learning with human approval</Text>
        <Text style={styles.rule}>✓ Micro-learning on every graded result</Text>
      </MetalPanel>

      <SectionTitle title="Recent Tickets" subtitle="Every active thesis remains visible." />
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
              label="OPEN TICKET"
              variant="outline"
              onPress={() => router.push(`/ticket/${ticket.id}`)}
            />
          </MetalPanel>
        ))
      ) : (
        <MetalPanel>
          <Text style={styles.panelTitle}>NO TICKET FORCED</Text>
          <Text style={type.body}>
            Run the slate when you are ready. If nothing qualifies, YWP OS will
            return PASS instead of manufacturing action.
          </Text>
        </MetalPanel>
      )}

      <Text style={styles.footer}>{brand.primaryLine}</Text>
      <Text style={styles.footerMuted}>{brand.secondaryLine}</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  engineHero: {
    height: 220,
    borderRadius: 18,
    overflow: "hidden",
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: "rgba(196,152,42,0.35)",
    backgroundColor: colors.backgroundRaised,
  },
  engineArt: {
    ...StyleSheet.absoluteFill,
    width: "100%",
    height: "100%",
  },
  engineScrim: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(5,5,5,0.55)",
  },
  engineCopy: {
    flex: 1,
    justifyContent: "flex-end",
    padding: spacing.lg,
    gap: spacing.xs,
  },
  hero: { padding: spacing.xl },
  brandMark: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 3,
  },
  heroTop: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md },
  heroCopy: { flex: 1, gap: spacing.xs },
  heroTitle: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 34,
    fontWeight: "800",
    letterSpacing: -0.6,
    lineHeight: 38,
  },
  heroText: { ...type.body, color: colors.silver },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  protocolHeader: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  panelTitle: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 18,
    fontWeight: "700",
  },
  rule: {
    color: colors.silver,
    fontFamily: fonts.body,
    fontSize: 14,
    lineHeight: 22,
  },
  ticketRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  ticketTitle: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 17,
    fontWeight: "700",
  },
  footer: {
    color: colors.gold,
    textAlign: "center",
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 2,
  },
  footerMuted: { ...type.caption, textAlign: "center", letterSpacing: 1.4 },
});
