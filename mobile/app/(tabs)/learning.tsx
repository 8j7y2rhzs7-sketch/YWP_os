import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { StatusPill } from "@/components/StatusPill";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing, type } from "@/theme";
import type {
  MissByOneReport,
  Performance,
  ProtocolDefinition,
} from "@/types";

interface Patterns {
  root_cause_tags: Array<{ tag: string; count: number }>;
  duplicate_thesis_losses: Array<{
    thesis_key: string;
    loss_count: number;
    recommendation_ids: string[];
  }>;
  recent_learning_events: Array<{
    event_type: string;
    sport: string | null;
    market_type: string | null;
    analysis: Record<string, unknown>;
    created_at: string;
  }>;
}

export default function LearningScreen() {
  const { request } = useAuth();
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [miss, setMiss] = useState<MissByOneReport | null>(null);
  const [patterns, setPatterns] = useState<Patterns | null>(null);
  const [protocol, setProtocol] = useState<ProtocolDefinition | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (refresh = false) => {
      refresh ? setRefreshing(true) : setLoading(true);
      setError(null);
      try {
        const [nextPerformance, nextMiss, nextPatterns, nextProtocol] =
          await Promise.all([
            request<Performance>("/learning/performance"),
            request<MissByOneReport>("/learning/miss-by-one"),
            request<Patterns>("/learning/patterns"),
            request<ProtocolDefinition>("/protocol/current"),
          ]);
        setPerformance(nextPerformance);
        setMiss(nextMiss);
        setPatterns(nextPatterns);
        setProtocol(nextProtocol);
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Learning data failed to load");
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
        <BrandHeader title="ADAPTIVE LEARNING" compact />
        <LoadingState label="Separating process from outcome…" />
      </Screen>
    );
  }

  return (
    <Screen refreshing={refreshing} onRefresh={() => void load(true)}>
      <BrandHeader title="ADAPTIVE LEARNING" subtitle="ALE • MISS-BY-1 • CALIBRATION" compact />
      {error ? <ErrorNotice message={error} /> : null}
      <MetalPanel tone="gold">
        <View style={styles.row}>
          <View style={styles.flex}>
            <Text style={type.eyebrow}>SELF-LEARNING PROTOCOL</Text>
            <Text style={styles.title}>Learn slowly. Never overreact.</Text>
          </View>
          <StatusPill value="LOCKED" />
        </View>
        <Text style={type.body}>
          Results create structured evidence. One win or loss can never rewrite
          production weights. Repeated patterns need a minimum sample, bounded
          changes, versioning, human approval, and rollback.
        </Text>
      </MetalPanel>

      <SectionTitle title="Performance" subtitle="Outcome metrics never replace process grading." />
      <MetalPanel>
        <View style={styles.metrics}>
          <Metric label="Settled" value={performance?.settled ?? 0} />
          <Metric label="Wins" value={performance?.wins ?? 0} accent={colors.success} />
          <Metric label="Losses" value={performance?.losses ?? 0} accent={colors.danger} />
          <Metric
            label="Win rate"
            value={
              performance?.win_rate === null || performance?.win_rate === undefined
                ? "—"
                : `${(performance.win_rate * 100).toFixed(1)}%`
            }
          />
          <Metric
            label="P/L"
            value={`$${Number(performance?.profit_loss ?? 0).toFixed(2)}`}
            accent={Number(performance?.profit_loss ?? 0) >= 0 ? colors.success : colors.danger}
          />
          <Metric
            label="ROI"
            value={performance?.roi === null || performance?.roi === undefined ? "—" : `${(performance.roi * 100).toFixed(1)}%`}
          />
        </View>
      </MetalPanel>

      <SectionTitle
        title="Miss-by-1 Lab"
        subtitle="Slips are counted separately from unique failed theses."
      />
      <MetalPanel tone={miss?.near_miss_results ? "danger" : "success"}>
        <View style={styles.metrics}>
          <Metric label="Near misses" value={miss?.near_miss_results ?? 0} accent={colors.warning} />
          <Metric label="Ticket killers" value={miss?.tickets_killed_by_near_miss ?? 0} accent={colors.danger} />
          <Metric label="Final losing leg" value={miss?.last_leg_near_misses ?? 0} accent={colors.danger} />
        </View>
        {(miss?.by_market ?? []).slice(0, 8).map((row, index) => (
          <View key={`${String(row.market_type)}-${index}`} style={styles.dataRow}>
            <Text style={styles.dataName}>{String(row.market_type ?? "unknown").replaceAll("_", " ")}</Text>
            <Text style={styles.dataValue}>{String(row.near_misses ?? 0)} near misses</Text>
          </View>
        ))}
        {!miss?.near_miss_results ? (
          <Text style={type.body}>No near-miss result has been graded yet.</Text>
        ) : null}
      </MetalPanel>

      <SectionTitle title="Recurring Root Causes" subtitle="Patterns are evidence, not automatic commands." />
      <MetalPanel>
        {patterns?.root_cause_tags.length ? (
          patterns.root_cause_tags.map((item) => (
            <View key={item.tag} style={styles.dataRow}>
              <Text style={styles.dataName}>{item.tag.replaceAll("_", " ")}</Text>
              <Text style={styles.count}>{item.count}</Text>
            </View>
          ))
        ) : (
          <Text style={type.body}>No recurring failure mode has enough logged evidence.</Text>
        )}
      </MetalPanel>

      <SectionTitle title="Confidence Calibration" subtitle="High ratings must earn high observed hit rates." />
      <MetalPanel>
        {performance?.confidence_calibration.length ? (
          performance.confidence_calibration.map((item) => (
            <View key={String(item.confidence_band)} style={styles.dataRow}>
              <Text style={styles.dataName}>Band {String(item.confidence_band)}</Text>
              <Text style={styles.dataValue}>
                {Number(item.observed_win_rate ?? 0) * 100}% observed • {String(item.settled)} settled
              </Text>
            </View>
          ))
        ) : (
          <Text style={type.body}>Calibration appears after graded results accumulate.</Text>
        )}
      </MetalPanel>

      <SectionTitle title="Guardrails" subtitle="These controls are part of the active protocol." />
      <MetalPanel tone="success">
        {(protocol?.adaptive_learning.guardrails ?? []).map((guardrail) => (
          <Text key={guardrail} style={styles.guardrail}>✓ {guardrail}</Text>
        ))}
      </MetalPanel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1, gap: spacing.xs },
  title: { color: colors.white, fontSize: 22, fontWeight: "900" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  dataRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
  },
  dataName: { flex: 1, color: colors.white, fontSize: 13, fontWeight: "800", textTransform: "uppercase" },
  dataValue: { color: colors.muted, fontSize: 12, textAlign: "right" },
  count: { color: colors.gold, fontSize: 20, fontWeight: "900" },
  guardrail: { color: colors.success, fontSize: 13, lineHeight: 20 },
});
