import { StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "@/theme";

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
  metric: { minWidth: 84, flex: 1, gap: spacing.xs },
  value: { fontSize: 22, fontWeight: "900" },
  label: {
    color: colors.muted,
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.7,
    textTransform: "uppercase",
  },
});
