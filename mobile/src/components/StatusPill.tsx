import { StyleSheet, Text, View } from "react-native";

import { colors, fonts, radius, spacing } from "@/theme";

const success = new Set(["PLAY", "LOCKED", "DOUBLE_CLEARED", "WIN", "POSITIVE", "SETTLED"]);
const warning = new Set(["LEAN", "WATCH", "WARNING", "PENDING", "PUSH", "VOID"]);
const danger = new Set(["SKIP", "REVIEW", "LOSS", "FAILED", "CHANGE_REQUIRED", "NEGATIVE"]);

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
    borderRadius: radius.sm,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  text: {
    fontFamily: fonts.bodyBold,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1.0,
  },
  success: { backgroundColor: colors.successDeep, borderColor: "rgba(63,219,150,0.55)" },
  warning: { backgroundColor: colors.warningDeep, borderColor: "rgba(255,184,62,0.55)" },
  danger: { backgroundColor: colors.dangerDeep, borderColor: "rgba(255,101,119,0.55)" },
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
