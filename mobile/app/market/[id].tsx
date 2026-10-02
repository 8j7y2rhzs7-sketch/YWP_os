import { useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MarketCallCard } from "@/components/MarketCallCard";
import { MetalPanel } from "@/components/MetalPanel";
import { Screen } from "@/components/Screen";
import { StatusPill } from "@/components/StatusPill";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing, type } from "@/theme";
import type { MarketCall } from "@/types";

function percent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export default function MarketDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { request } = useAuth();
  const [call, setCall] = useState<MarketCall | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setCall(await request<MarketCall>(`/markets/calls/${id}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load this call");
    } finally {
      setLoading(false);
    }
  }, [id, request]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <Screen>
        <LoadingState label="Opening the call…" />
      </Screen>
    );
  }

  if (!call) {
    return (
      <Screen>
        <ErrorNotice message={error ?? "This call is not on the board."} />
      </Screen>
    );
  }

  return (
    <Screen>
      {error ? <ErrorNotice message={error} /> : null}
      <MarketCallCard item={call} />
      <MetalPanel>
        <View style={styles.row}>
          <Text style={type.eyebrow}>GRADE</Text>
          <StatusPill value={call.outcome ?? "PENDING"} />
        </View>
        <Text style={styles.line}>Entry {call.entry ?? "—"}</Text>
        <Text style={styles.line}>Target {call.target ?? "—"}</Text>
        <Text style={styles.line}>Stop {call.stop ?? "—"}</Text>
        <Text style={styles.line}>Model {percent(call.model_probability)}</Text>
        <Text style={styles.line}>Fair / break-even {percent(call.fair_price)}</Text>
        <Text style={styles.line}>Market price after fees {percent(call.market_price)}</Text>
        <Text style={styles.line}>Edge after fees {percent(call.edge)}</Text>
        {call.reasons.map((reason) => (
          <Text key={reason} style={styles.reason}>
            {reason}
          </Text>
        ))}
        <Text style={type.caption}>Read only. This screen does not send an order.</Text>
      </MetalPanel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: spacing.md,
  },
  line: { color: colors.text, fontSize: 14 },
  reason: { color: colors.muted, fontSize: 14, lineHeight: 20 },
});
