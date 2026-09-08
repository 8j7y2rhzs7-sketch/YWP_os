import { StyleSheet, Text, View } from "react-native";

import { colors, fonts, radius, spacing } from "@/theme";

export function Metric({
  label,
  value,
  accent = colors.gold,
}: {
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <View style={styles.metric}>
      <Text style={[styles.value, { color: accent }]} numberOfLines={1}>
        {value}
      </Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  metric: {
    minWidth: 96,
    flex: 1,
    gap: 6,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    borderRadius: radius.sm,
    backgroundColor: "rgba(255,255,255,0.035)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.08)",
  },
  value: {
    fontFamily: fonts.displaySemi,
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: -0.6,
  },
  label: {
    color: colors.muted,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.7,
    textTransform: "uppercase",
  },
});
