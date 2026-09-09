import { useEffect, useRef } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";

import { CountUp } from "@/components/CountUp";
import { useReduceMotion } from "@/hooks/useReduceMotion";
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
  const reduceMotion = useReduceMotion();
  const pop = useRef(new Animated.Value(reduceMotion ? 1 : 0)).current;
  const numeric = typeof value === "number" ? value : null;

  useEffect(() => {
    if (reduceMotion) {
      pop.setValue(1);
      return;
    }
    pop.setValue(0);
    Animated.spring(pop, {
      toValue: 1,
      friction: 5,
      tension: 160,
      useNativeDriver: true,
    }).start();
  }, [pop, reduceMotion, value]);

  return (
    <Animated.View
      style={[
        styles.metric,
        {
          opacity: pop,
          transform: [
            {
              scale: pop.interpolate({
                inputRange: [0, 1],
                outputRange: [0.78, 1],
              }),
            },
            {
              translateY: pop.interpolate({
                inputRange: [0, 1],
                outputRange: [10, 0],
              }),
            },
          ],
        },
      ]}
    >
      {numeric === null ? (
        <Text style={[styles.value, { color: accent }]} numberOfLines={1}>
          {value}
        </Text>
      ) : (
        <CountUp value={numeric} style={{ ...styles.value, color: accent }} />
      )}
      <Text style={styles.label}>{label}</Text>
    </Animated.View>
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
