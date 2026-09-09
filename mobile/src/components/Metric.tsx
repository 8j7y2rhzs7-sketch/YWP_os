import { useEffect, useRef } from "react";
import { Animated, StyleSheet, Text } from "react-native";

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

  useEffect(() => {
    if (reduceMotion) {
      pop.setValue(1);
      return;
    }
    pop.setValue(0);
    Animated.spring(pop, {
      toValue: 1,
      friction: 6,
      tension: 140,
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
                outputRange: [0.86, 1],
              }),
            },
          ],
        },
      ]}
    >
      <Text style={[styles.value, { color: accent }]} numberOfLines={1}>
        {value}
      </Text>
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
