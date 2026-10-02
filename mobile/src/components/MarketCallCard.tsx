import { Pressable, StyleSheet, Text, View } from "react-native";

import { MetalPanel } from "@/components/MetalPanel";
import { StatusPill } from "@/components/StatusPill";
import { colors, spacing, type } from "@/theme";
import type { MarketCall } from "@/types";

function percent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function MarketCallCard({
  item,
  onPress,
}: {
  item: MarketCall;
  onPress?: () => void;
}) {
  const quiet = item.verdict === "SKIP" || item.verdict === "WAIT" || item.verdict === "REVIEW";
  const body = (
    <MetalPanel tone={quiet ? "danger" : "default"} style={styles.panel} animate={false}>
      <View style={styles.top}>
        <View style={styles.titleWrap}>
          <Text style={styles.market}>
            {item.venue.toUpperCase()} · {item.call_type.replaceAll("_", " ")}
          </Text>
          <Text style={styles.selection}>{item.title}</Text>
          <Text style={type.caption}>{item.selection}</Text>
        </View>
        <StatusPill value={item.verdict} />
      </View>
      <View style={styles.metrics}>
        <Text style={styles.metric}>MODEL {percent(item.model_probability)}</Text>
        <Text style={styles.metric}>FAIR {percent(item.fair_price)}</Text>
        <Text style={styles.metric}>EDGE {percent(item.edge)}</Text>
      </View>
      {item.reasons.slice(0, 3).map((reason) => (
        <Text key={reason} style={styles.reason}>
          {reason}
        </Text>
      ))}
      {item.price_gap ? (
        <Text style={styles.gap}>
          PRICE GAP {(item.price_gap.gap * 100).toFixed(1)} pts · signal only, not a play
        </Text>
      ) : null}
      <Text style={styles.badge}>READ ONLY</Text>
    </MetalPanel>
  );
  if (!onPress) return body;
  return (
    <Pressable accessibilityRole="button" onPress={onPress}>
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  panel: { gap: spacing.sm },
  top: { flexDirection: "row", justifyContent: "space-between", gap: spacing.md },
  titleWrap: { flex: 1, gap: 2 },
  market: {
    color: colors.gold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.6,
  },
  selection: { color: colors.text, fontSize: 16, fontWeight: "700" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  metric: { color: colors.silver, fontSize: 12, fontWeight: "700", letterSpacing: 0.4 },
  reason: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  gap: { color: colors.circuitBlueBright, fontSize: 12, lineHeight: 18 },
  badge: {
    alignSelf: "flex-start",
    color: colors.gold,
    borderColor: colors.borderGold,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 3,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.8,
  },
});
