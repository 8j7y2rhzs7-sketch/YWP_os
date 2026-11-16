import { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, Text, View } from "react-native";

import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors, fonts, radius, spacing, type, registerStyles } from "@/theme";

export type RunActivityPhase = "loading" | "warming" | "analyzing" | "queued" | "idle";

export type RunActivity = {
  phase: RunActivityPhase;
  /** 0–100 when known; null = indeterminate pulse. */
  pct: number | null;
  title: string;
  detail: string;
  icon: string;
};

type Props = {
  activity: RunActivity | null;
  accent?: string;
};

/**
 * Sticky “what’s happening” strip for Run — bars + icon + live copy so a
 * multi-minute ALL / warm / grade never feels frozen.
 */
export function RunActivityBanner({ activity, accent = colors.circuitBlueBright }: Props) {
  const reduceMotion = useReduceMotion();
  const pulse = useRef(new Animated.Value(0)).current;
  const enter = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!activity || activity.phase === "idle") {
      enter.setValue(0);
      return;
    }
    Animated.spring(enter, {
      toValue: 1,
      friction: 8,
      tension: 70,
      useNativeDriver: true,
    }).start();
  }, [activity?.phase, activity?.title, enter]);

  useEffect(() => {
    if (!activity || activity.phase === "idle" || reduceMotion) {
      pulse.setValue(0.4);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 900,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: false,
        }),
        Animated.timing(pulse, {
          toValue: 0.25,
          duration: 900,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: false,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [activity?.phase, pulse, reduceMotion]);

  if (!activity || activity.phase === "idle") return null;

  const known = activity.pct != null && Number.isFinite(activity.pct);
  const fillPct = known
    ? Math.max(2, Math.min(100, Number(activity.pct)))
    : 0;
  const fillWidth = `${fillPct}%` as `${number}%`;
  const fillColor =
    activity.phase === "analyzing"
      ? colors.gold
      : activity.phase === "queued"
        ? colors.goldBright
        : accent;

  return (
    <Animated.View
      style={[
        styles.wrap,
        {
          borderColor: fillColor,
          opacity: enter,
          transform: [
            {
              translateY: enter.interpolate({
                inputRange: [0, 1],
                outputRange: [-10, 0],
              }),
            },
          ],
        },
      ]}
      accessibilityRole="progressbar"
      accessibilityValue={
        known
          ? { now: Math.round(activity.pct ?? 0), min: 0, max: 100 }
          : undefined
      }
      accessibilityLabel={`${activity.title}. ${activity.detail}`}
    >
      <View style={styles.row}>
        <View style={[styles.iconBadge, { borderColor: fillColor }]}>
          <Text style={styles.icon}>{activity.icon}</Text>
        </View>
        <View style={styles.copy}>
          <Text style={[styles.title, { color: fillColor }]} numberOfLines={1}>
            {activity.title}
          </Text>
          <Text style={styles.detail} numberOfLines={2}>
            {activity.detail}
          </Text>
        </View>
        <Text style={[styles.pct, { color: fillColor }]}>
          {known ? `${Math.round(activity.pct ?? 0)}%` : "•••"}
        </Text>
      </View>
      <View style={styles.track}>
        {known ? (
          <View
            style={[
              styles.fill,
              { width: fillWidth, backgroundColor: fillColor },
            ]}
          />
        ) : (
          <Animated.View
            style={[
              styles.indeterminate,
              {
                backgroundColor: fillColor,
                opacity: pulse,
                transform: [
                  {
                    translateX: pulse.interpolate({
                      inputRange: [0.25, 1],
                      outputRange: [-40, 120],
                    }),
                  },
                ],
              },
            ]}
          />
        )}
      </View>
    </Animated.View>
  );
}

const styles = registerStyles(() =>
  StyleSheet.create({
    wrap: {
      marginHorizontal: spacing.md,
      marginBottom: spacing.sm,
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      borderRadius: radius.md,
      borderWidth: StyleSheet.hairlineWidth,
      backgroundColor: "rgba(6,12,20,0.94)",
      gap: spacing.sm,
    },
    row: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.sm,
    },
    iconBadge: {
      width: 36,
      height: 36,
      borderRadius: 18,
      borderWidth: StyleSheet.hairlineWidth,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "rgba(255,255,255,0.04)",
    },
    icon: {
      fontSize: 18,
      lineHeight: 22,
    },
    copy: {
      flex: 1,
      gap: 2,
      minWidth: 0,
    },
    title: {
      fontFamily: fonts.bodyBold,
      fontSize: 12,
      letterSpacing: 1.1,
      fontWeight: "700",
      textTransform: "uppercase",
    },
    detail: {
      ...type.caption,
      color: colors.silver,
    },
    pct: {
      fontFamily: fonts.displaySemi,
      fontSize: 16,
      fontWeight: "700",
      minWidth: 44,
      textAlign: "right",
    },
    track: {
      height: 6,
      borderRadius: 3,
      overflow: "hidden",
      backgroundColor: "rgba(255,255,255,0.08)",
    },
    fill: {
      height: "100%",
      borderRadius: 3,
    },
    indeterminate: {
      width: "38%",
      height: "100%",
      borderRadius: 3,
    },
  }),
);
