import { StyleSheet, Text, View } from "react-native";

import { colors, spacing, type } from "@/theme";
import type { HiveLearningSummary } from "@/types";

type Props = {
  hive?: HiveLearningSummary | null;
  /** Fallback when only the scalar pct is present on older payloads. */
  optimumAccuracyPct?: number | null;
};

function statusLabel(status?: string): string {
  switch (status) {
    case "optimal":
      return "OPTIMAL";
    case "calibrating":
      return "CALIBRATING";
    case "collecting":
      return "COLLECTING";
    default:
      return "BUILDING";
  }
}

export function HiveAccuracyMeter({ hive, optimumAccuracyPct }: Props) {
  const pct = Math.max(
    0,
    Math.min(100, Number(hive?.optimum_accuracy_pct ?? optimumAccuracyPct ?? 0)),
  );
  const eligible = hive?.eligible_samples ?? 0;
  const optimal = hive?.optimal_sample ?? 200;
  const pending = hive?.pending_samples ?? 0;
  const volume = hive?.volume_score_pct ?? null;
  const calibration = hive?.calibration_score_pct ?? null;
  const active = hive?.calibration_active ?? eligible >= (hive?.min_sample_for_calibration ?? 40);
  const fillColor =
    pct >= 100 ? colors.success : pct >= 40 ? colors.gold : colors.warning;

  return (
    <View style={styles.wrap} accessibilityRole="progressbar" accessibilityValue={{ now: pct, min: 0, max: 100 }}>
      <View style={styles.header}>
        <Text style={type.eyebrow}>HIVE OPTIMUM ACCURACY</Text>
        <Text style={[styles.pct, { color: fillColor }]}>{pct.toFixed(1)}%</Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${pct}%`, backgroundColor: fillColor }]} />
        {/* Calibration unlock marker at 40% of the meter scale */}
        <View style={[styles.marker, { left: "40%" }]} />
      </View>
      <View style={styles.metaRow}>
        <Text style={styles.meta}>{statusLabel(hive?.status)}</Text>
        <Text style={styles.meta}>
          {eligible}/{optimal} settled
          {pending ? ` · ${pending} pending sync` : ""}
        </Text>
      </View>
      {volume != null && calibration != null ? (
        <Text style={styles.formula}>
          Volume {volume.toFixed(1)}% + calibration {calibration.toFixed(1)}%
          {active ? " · blend active" : " · blend locked until min sample"}
        </Text>
      ) : (
        <Text style={styles.formula}>
          Calculated from settled Hive outcomes vs {optimal}-sample optimum
          {active ? "" : " · blend locked until min sample"}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing.xs,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  pct: {
    fontSize: 18,
    fontWeight: "900",
    letterSpacing: 0.4,
  },
  track: {
    height: 10,
    borderRadius: 999,
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
    position: "relative",
  },
  fill: {
    height: "100%",
    borderRadius: 999,
  },
  marker: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: 2,
    marginLeft: -1,
    backgroundColor: "rgba(255,255,255,0.28)",
  },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  meta: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  formula: {
    color: colors.dim,
    fontSize: 11,
    lineHeight: 15,
  },
});
