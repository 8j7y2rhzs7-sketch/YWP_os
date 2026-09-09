import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { EngineOrbit } from "@/components/EngineOrbit";
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
        <View style={styles.heroViewport}>
          <EngineOrbit size={200} tone="loading" label="Booting" />
          <Text style={styles.brandMark}>{brand.product}</Text>
          <LoadingState label="Decision Engine warming…" />
        </View>
      </Screen>
    );
  }

  const support =
    pulse?.headline ??
    "Run a slate, lock a ticket, grade a result. Edge over noise.";

  return (
    <Screen refreshing={refreshing} onRefresh={() => void load(true)}>
      {/* First viewport: one composition — brand, headline, support, CTA, focal engine */}
      <View style={styles.heroViewport}>
        <EngineOrbit size={236} tone="idle" />
        <Text style={styles.brandMark}>{brand.product}</Text>
        <Text style={styles.heroTitle}>Your winning process.</Text>
        <Text style={styles.heroSupport} numberOfLines={2}>
          {support}
        </Text>
        <View style={styles.ctaGroup}>
          <YwpButton
            label="RUN TODAY'S FULL PROTOCOL"
            onPress={() => router.push("/(tabs)/slate")}
          />
          <Text style={styles.welcome}>
            Welcome back, {user?.name ?? "operator"} · {brand.skin}
          </Text>
        </View>
      </View>

      {error ? <ErrorNotice message={error} /> : null}

      <SectionTitle
        title="Session pulse"
        subtitle="Bankroll and Hive signals sit below the engine — not on top of it."
      />
      <MetalPanel tone="gold">
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
      </MetalPanel>

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
          <StatusPill
            value={(protocol?.status ?? "standby").toUpperCase().replace(/_/g, " ")}
          />
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
  heroViewport: {
    minHeight: 520,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    paddingTop: spacing.xl,
    paddingBottom: spacing.xxl,
  },
  brandMark: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 42,
    fontWeight: "800",
    letterSpacing: -1.4,
    textAlign: "center",
    marginTop: spacing.sm,
  },
  heroTitle: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 24,
    fontWeight: "800",
    letterSpacing: -0.6,
    lineHeight: 28,
    textAlign: "center",
  },
  heroSupport: {
    ...type.body,
    color: colors.silver,
    textAlign: "center",
    maxWidth: 340,
    paddingHorizontal: spacing.md,
  },
  ctaGroup: {
    width: "100%",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  welcome: {
    ...type.caption,
    textAlign: "center",
    color: colors.dim,
    letterSpacing: 0.4,
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
  rule: {
    color: colors.silver,
    fontFamily: fonts.body,
    fontSize: 15,
    lineHeight: 23,
    letterSpacing: -0.1,
  },
  ticketRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  ticketTitle: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: -0.25,
  },
  footer: {
    color: colors.gold,
    textAlign: "center",
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.2,
  },
  footerMuted: { ...type.caption, textAlign: "center", letterSpacing: 0.6 },
});
