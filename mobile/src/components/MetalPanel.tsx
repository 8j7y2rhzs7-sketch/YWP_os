import { useEffect, useRef, type ReactNode } from "react";
import {
  Animated,
  Easing,
  StyleSheet,
  type StyleProp,
  View,
  type ViewStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { MetalShimmer } from "@/components/MetalShimmer";
import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors, gradients, radius, shadow, spacing } from "@/theme";

interface MetalPanelProps {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  tone?: "default" | "success" | "danger" | "gold";
  accent?: string;
  /** Stagger entrance when many panels mount together. */
  motionDelay?: number;
  /** Soft enter animation (on by default for whole-app motion). */
  animate?: boolean;
}

export function MetalPanel({
  children,
  style,
  tone = "default",
  accent,
  motionDelay = 0,
  animate = true,
}: MetalPanelProps) {
  const reduceMotion = useReduceMotion();
  const enter = useRef(new Animated.Value(animate && !reduceMotion ? 0 : 1)).current;

  useEffect(() => {
    if (!animate || reduceMotion) {
      enter.setValue(1);
      return;
    }
    enter.setValue(0);
    const anim = Animated.timing(enter, {
      toValue: 1,
      duration: 420,
      delay: motionDelay,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    });
    anim.start();
    return () => anim.stop();
  }, [animate, enter, motionDelay, reduceMotion, tone]);

  const palette =
    tone === "success"
      ? gradients.success
      : tone === "danger"
        ? gradients.danger
        : tone === "gold"
          ? gradients.panelGold
          : gradients.panel;
  const edgeColor =
    tone === "success"
      ? colors.success
      : tone === "danger"
        ? colors.danger
        : tone === "gold"
          ? colors.gold
          : accent ?? colors.circuitBlue;

  const body = (
    <LinearGradient
      colors={palette}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={[
        styles.panel,
        tone === "success" && styles.success,
        tone === "danger" && styles.danger,
        tone === "gold" && styles.gold,
        style,
      ]}
    >
      <View style={[styles.edge, { backgroundColor: edgeColor }]} />
      <View style={styles.highlight} />
      {tone === "gold" ? (
        <MetalShimmer intensity="soft" periodMs={4200} style={styles.sheenShimmer}>
          <View style={styles.glassSheenFill} />
        </MetalShimmer>
      ) : (
        <View style={styles.glassSheen} />
      )}
      {children}
    </LinearGradient>
  );

  if (!animate) return body;

  return (
    <Animated.View
      style={{
        opacity: enter,
        transform: [
          {
            translateY: enter.interpolate({
              inputRange: [0, 1],
              outputRange: [14, 0],
            }),
          },
        ],
      }}
    >
      {body}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  panel: {
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,255,255,0.12)",
    padding: spacing.xl,
    gap: spacing.lg,
    overflow: "hidden",
    ...shadow,
  },
  edge: {
    position: "absolute",
    left: 0,
    top: 14,
    bottom: 14,
    width: 3,
    borderRadius: 2,
    opacity: 0.85,
  },
  highlight: {
    position: "absolute",
    top: 0,
    left: 20,
    right: 20,
    height: StyleSheet.hairlineWidth,
    backgroundColor: "rgba(255,255,255,0.22)",
  },
  glassSheen: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 48,
    backgroundColor: colors.glass,
  },
  glassSheenFill: {
    height: 48,
    backgroundColor: colors.glass,
  },
  sheenShimmer: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 48,
  },
  success: { borderColor: "rgba(46,229,154,0.4)" },
  danger: { borderColor: "rgba(255,77,106,0.4)" },
  gold: { borderColor: "rgba(196,152,42,0.5)" },
});
