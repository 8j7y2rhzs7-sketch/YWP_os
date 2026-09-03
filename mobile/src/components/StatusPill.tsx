import { StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "@/theme";

const success = new Set(["PLAY", "LOCKED", "DOUBLE_CLEARED", "WIN", "POSITIVE"]);
const warning = new Set(["LEAN", "WATCH", "WARNING", "PENDING"]);
const danger = new Set(["SKIP", "LOSS", "FAILED", "CHANGE_REQUIRED", "NEGATIVE"]);

export function StatusPill({ value }: { value: string }) {
  const normalized = value.toUpperCase();
  const tone = success.has(normalized)
    ? "success"
    : danger.has(normalized)
      ? "danger"
      : warning.has(normalized)
        ? "warning"
        : "neutral";
  return (
    <View style={[styles.pill, styles[tone]]}>
      <View style={[styles.dot, styles[`${tone}Dot`]]} />
      <Text style={[styles.text, styles[`${tone}Text`]]}>{normalized}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: 7,
  },
  dot: { width: 7, height: 7, borderRadius: 4 },
  text: { fontSize: 11, fontWeight: "900", letterSpacing: 0.8 },
  success: { backgroundColor: colors.successDeep, borderColor: colors.success },
  warning: { backgroundColor: colors.warningDeep, borderColor: colors.warning },
  danger: { backgroundColor: colors.dangerDeep, borderColor: colors.danger },
  neutral: { backgroundColor: colors.surfaceRaised, borderColor: colors.border },
  successDot: { backgroundColor: colors.success },
  warningDot: { backgroundColor: colors.warning },
  dangerDot: { backgroundColor: colors.danger },
  neutralDot: { backgroundColor: colors.silver },
  successText: { color: colors.success },
  warningText: { color: colors.warning },
  dangerText: { color: colors.danger },
  neutralText: { color: colors.silver },
});
