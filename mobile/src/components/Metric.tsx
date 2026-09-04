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
      <Text style={[styles.value, { color: accent }]}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  metric: {
    minWidth: 88,
    flex: 1,
    gap: 4,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: "rgba(255,255,255,0.03)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.06)",
  },
  value: {
    fontFamily: fonts.displaySemi,
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: -0.3,
  },
  label: {
    color: colors.muted,
    fontFamily: fonts.bodyBold,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
});
