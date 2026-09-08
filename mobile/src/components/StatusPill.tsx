import { useEffect, useRef } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";

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
  const stamp = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    stamp.setValue(0);
    Animated.spring(stamp, {
      toValue: 1,
      friction: 6,
      tension: 120,
      useNativeDriver: true,
    }).start();
  }, [normalized, stamp]);

  return (
    <Animated.View
      style={[
        styles.pill,
        styles[tone],
        {
          opacity: stamp,
          transform: [
            {
              scale: stamp.interpolate({
                inputRange: [0, 1],
                outputRange: [0.9, 1],
              }),
            },
          ],
        },
      ]}
    >
      <View style={[styles.dot, styles[`${tone}Dot`]]} />
      <Text style={[styles.text, styles[`${tone}Text`]]}>{normalized}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  pill: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 12,
    paddingVertical: 7,
    minHeight: 28,
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  text: {
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.7,
  },
  success: { backgroundColor: colors.successDeep, borderColor: "rgba(46,229,154,0.55)" },
  warning: { backgroundColor: colors.warningDeep, borderColor: "rgba(255,176,32,0.55)" },
  danger: { backgroundColor: colors.dangerDeep, borderColor: "rgba(255,77,106,0.55)" },
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
