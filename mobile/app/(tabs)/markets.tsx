import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MarketCallCard } from "@/components/MarketCallCard";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { useAuth } from "@/context/AuthContext";
import { colors, radius, spacing, type } from "@/theme";
import type { MarketCallList, MarketsHealth, MarketsTrackRecord } from "@/types";

type Venue = "crypto" | "sports_exchange";

function percent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export default function MarketsScreen() {
  const { request } = useAuth();
  const [venue, setVenue] = useState<Venue>("crypto");
  const [board, setBoard] = useState<MarketCallList | null>(null);
  const [record, setRecord] = useState<MarketsTrackRecord | null>(null);
  const [health, setHealth] = useState<MarketsHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (refresh = false) => {
      refresh ? setRefreshing(true) : setLoading(true);
      setError(null);
      try {
        const [nextBoard, nextRecord, nextHealth] = await Promise.all([
          request<MarketCallList>(`/markets/calls?venue=${venue}`),
          request<MarketsTrackRecord>(`/markets/performance?venue=${venue}`),
          request<MarketsHealth>("/markets/health"),
        ]);
        setBoard(nextBoard);
        setRecord(nextRecord);
        setHealth(nextHealth);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Markets board failed to load");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [request, venue],
  );

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <Screen>
        <BrandHeader title="MARKETS" subtitle="READ ONLY" compact />
        <LoadingState label="Loading public prices…" />
      </Screen>
    );
  }

  const calls = board?.calls ?? [];
  return (
    <Screen refreshing={refreshing} onRefresh={() => void load(true)}>
      <BrandHeader title="MARKETS" subtitle="PUBLIC PRICES · NO ORDERS" compact />
      {error ? <ErrorNotice message={error} /> : null}
      <View style={styles.toggle}>
        <Pressable
          accessibilityRole="button"
          onPress={() => setVenue("crypto")}
          style={[styles.toggleItem, venue === "crypto" && styles.toggleOn]}
        >
          <Text style={[styles.toggleText, venue === "crypto" && styles.toggleTextOn]}>Crypto</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          onPress={() => setVenue("sports_exchange")}
          style={[styles.toggleItem, venue === "sports_exchange" && styles.toggleOn]}
        >
          <Text style={[styles.toggleText, venue === "sports_exchange" && styles.toggleTextOn]}>
            Sports Exchange
          </Text>
        </Pressable>
      </View>
      <MetalPanel tone="gold">
        <Text style={type.eyebrow}>TRACK RECORD</Text>
        <Text style={styles.note}>{record?.note ?? "Markets grades stay separate from sports."}</Text>
        <View style={styles.metrics}>
          <Metric label="CALLS" value={record?.n_calls ?? 0} />
          <Metric label="GRADED" value={record?.n_graded ?? 0} />
          <Metric label="HIT RATE" value={percent(record?.hit_rate)} />
          <Metric label="EV AFTER FEES" value={percent(record?.mean_ev)} />
        </View>
        <Text style={type.caption}>
          {health?.enabled
            ? "Read-only mode is on. Nothing on this screen can place a trade."
            : "Markets mode is switched off."}
        </Text>
      </MetalPanel>
      <SectionTitle
        title={venue === "crypto" ? "CRYPTO BRACKETS" : "SPORTS EXCHANGE"}
        subtitle="Verdict, edge after fees, and why"
      />
      {calls.length === 0 ? (
        <MetalPanel>
          <Text style={styles.empty}>
            No calls yet. Pull down and the phone reads public prices on its own. Nothing on this
            screen buys or sells.
          </Text>
        </MetalPanel>
      ) : (
        calls.map((item) => (
          <MarketCallCard
            key={item.id}
            item={item}
            onPress={() => router.push(`/market/${item.id}`)}
          />
        ))
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  toggle: {
    flexDirection: "row",
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: 4,
  },
  toggleItem: {
    flex: 1,
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.md,
  },
  toggleOn: { backgroundColor: colors.goldMute },
  toggleText: { color: colors.dim, fontSize: 13, fontWeight: "700" },
  toggleTextOn: { color: colors.goldBright },
  note: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  empty: { color: colors.text, fontSize: 15, lineHeight: 22 },
});
