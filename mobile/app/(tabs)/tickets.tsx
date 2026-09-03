import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing, type } from "@/theme";
import type { Ticket } from "@/types";

export default function TicketsScreen() {
  const { request } = useAuth();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (refresh = false) => {
      refresh ? setRefreshing(true) : setLoading(true);
      setError(null);
      try {
        setTickets(await request<Ticket[]>("/tickets?limit=100"));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Tickets failed to load");
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

  return (
    <Screen refreshing={refreshing} onRefresh={() => void load(true)}>
      <BrandHeader title="TICKET VAULT" subtitle="EXPOSURE • LOCKS • DECISIONS" compact />
      {error ? <ErrorNotice message={error} /> : null}
      {loading ? <LoadingState label="Loading protected tickets…" /> : null}
      {!loading && !tickets.length ? (
        <MetalPanel tone="gold">
          <StatusPill value="PASS" />
          <Text style={styles.title}>No tickets saved.</Text>
          <Text style={type.body}>
            This is clean exposure. Run the protocol when a verified slate is ready.
          </Text>
          <YwpButton label="RUN A SLATE" onPress={() => router.push("/(tabs)/slate")} />
        </MetalPanel>
      ) : null}
      {tickets.map((ticket) => (
        <MetalPanel key={ticket.id} tone={ticket.status === "placed" ? "success" : "default"}>
          <View style={styles.row}>
            <View style={styles.flex}>
              <Text style={type.eyebrow}>{ticket.ticket_type.replaceAll("_", " ")}</Text>
              <Text style={styles.title}>{ticket.label}</Text>
              <Text style={type.caption}>
                {ticket.sport.toUpperCase()} • {ticket.slate_date} • {ticket.legs.length} legs
              </Text>
            </View>
            <StatusPill value={ticket.last_lock_status ?? ticket.status} />
          </View>
          <View style={styles.metrics}>
            <Metric label="Stake" value={`$${ticket.stake}`} />
            <Metric label="Potential" value={`$${ticket.potential_payout}`} accent={colors.success} />
            <Metric label="Confidence" value={`${ticket.confidence_score}%`} />
          </View>
          {ticket.legs.map((leg) => (
            <View key={leg.id} style={styles.leg}>
              <Text style={styles.legNumber}>{leg.position}</Text>
              <Text style={styles.selection}>{leg.selection}</Text>
              <Text style={styles.odds}>
                {leg.american_odds > 0 ? "+" : ""}
                {leg.american_odds}
              </Text>
            </View>
          ))}
          <YwpButton
            label="OPEN LOCK CENTER"
            variant="outline"
            onPress={() => router.push(`/ticket/${ticket.id}`)}
          />
        </MetalPanel>
      ))}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1, gap: 2 },
  title: { color: colors.white, fontSize: 20, fontWeight: "900" },
  metrics: { flexDirection: "row", gap: spacing.md, flexWrap: "wrap" },
  leg: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
  },
  legNumber: { color: colors.gold, fontWeight: "900" },
  selection: { flex: 1, color: colors.white, fontWeight: "800" },
  odds: { color: colors.gold, fontWeight: "900" },
});
