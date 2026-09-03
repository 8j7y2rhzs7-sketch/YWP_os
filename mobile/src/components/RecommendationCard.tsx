import { StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, type } from "@/theme";
import type { Recommendation } from "@/types";

import { MetalPanel } from "./MetalPanel";
import { StatusPill } from "./StatusPill";

function odds(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}

export function RecommendationCard({
  item,
  compact = false,
}: {
  item: Recommendation;
  compact?: boolean;
}) {
  const skip = item.decision === "SKIP";
  return (
    <MetalPanel tone={skip ? "danger" : "default"} style={styles.panel}>
      <View style={styles.top}>
        <View style={styles.rank}>
          <Text style={styles.rankText}>{item.rank}</Text>
        </View>
        <View style={styles.titleWrap}>
          <Text style={styles.market}>
            {item.sport.toUpperCase()} • {item.market_type.replaceAll("_", " ")}
          </Text>
          <Text style={styles.selection}>{item.selection}</Text>
          <Text style={type.caption}>{item.event_name}</Text>
        </View>
        <View style={styles.right}>
          <Text style={styles.odds}>{odds(item.american_odds)}</Text>
          <Text style={styles.rating}>YIS {item.ywp_rating}</Text>
        </View>
      </View>
      <View style={styles.statusRow}>
        <StatusPill value={item.decision} />
        <Text style={styles.confidence}>{item.confidence_score}% CONFIDENCE</Text>
        <Text style={styles.vision}>VISION {item.vision_score}</Text>
      </View>
      {!compact ? (
        <>
          <Text style={styles.reasoning}>{item.reasoning_summary}</Text>
          <View style={styles.tags}>
            {item.reason_codes.slice(0, 4).map((code) => (
              <Text key={code} style={styles.tag}>
                {code.replaceAll("_", " ")}
              </Text>
            ))}
          </View>
          {item.warnings.length ? (
            <View style={styles.warningBox}>
              {item.warnings.slice(0, 3).map((warning) => (
                <Text key={warning} style={styles.warningText}>
                  ⚠ {warning}
                </Text>
              ))}
            </View>
          ) : null}
          {item.safer_alternative ? (
            <Text style={styles.safer}>SAFER: {item.safer_alternative}</Text>
          ) : null}
          {item.live_trigger ? (
            <Text style={styles.live}>LIVE TRIGGER: {item.live_trigger}</Text>
          ) : null}
          {item.hedge ? (
            <Text style={styles.hedge}>HEDGE / CASH-OUT: {item.hedge}</Text>
          ) : null}
        </>
      ) : null}
    </MetalPanel>
  );
}

const styles = StyleSheet.create({
  panel: { padding: spacing.md },
  top: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  rank: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.gold,
  },
  rankText: { color: colors.background, fontWeight: "900", fontSize: 16 },
  titleWrap: { flex: 1, gap: 2 },
  market: {
    color: colors.success,
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 1.2,
    textTransform: "uppercase",
  },
  selection: { color: colors.white, fontSize: 17, fontWeight: "800" },
  right: { alignItems: "flex-end", gap: 3 },
  odds: { color: colors.gold, fontSize: 16, fontWeight: "900" },
  rating: {
    backgroundColor: colors.gold,
    color: colors.background,
    fontSize: 10,
    fontWeight: "900",
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radius.sm,
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  confidence: { color: colors.white, fontSize: 11, fontWeight: "900" },
  vision: { color: colors.gold, fontSize: 11, fontWeight: "900" },
  reasoning: { ...type.body, color: colors.silver },
  tags: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  tag: {
    color: colors.muted,
    fontSize: 9,
    fontWeight: "800",
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
  },
  warningBox: {
    backgroundColor: colors.dangerDeep,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.xs,
  },
  warningText: { color: colors.danger, fontSize: 12, lineHeight: 17 },
  safer: { color: colors.success, fontSize: 12, fontWeight: "800" },
  live: { color: colors.info, fontSize: 12, lineHeight: 17, fontWeight: "800" },
  hedge: { color: colors.warning, fontSize: 12, lineHeight: 17, fontWeight: "800" },
});
