import type { ReactNode } from "react";
import {
  StyleSheet,
  type StyleProp,
  View,
  type ViewStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { colors, gradients, radius, shadow, spacing } from "@/theme";

interface MetalPanelProps {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  tone?: "default" | "success" | "danger" | "gold";
  accent?: string;
}

export function MetalPanel({
  children,
  style,
  tone = "default",
  accent,
}: MetalPanelProps) {
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
          : accent ?? colors.goldMute;
  return (
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
      <View style={styles.glassSheen} />
      {children}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  panel: {
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.1)",
    padding: spacing.lg,
    gap: spacing.md,
    overflow: "hidden",
    ...shadow,
  },
  edge: {
    position: "absolute",
    left: 0,
    top: 12,
    bottom: 12,
    width: 3,
    borderRadius: 2,
    opacity: 0.9,
  },
  highlight: {
    position: "absolute",
    top: 0,
    left: 18,
    right: 18,
    height: StyleSheet.hairlineWidth,
    backgroundColor: "rgba(255,255,255,0.28)",
  },
  glassSheen: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 42,
    backgroundColor: colors.glass,
  },
  success: { borderColor: "rgba(46,229,154,0.45)" },
  danger: { borderColor: "rgba(255,77,106,0.45)" },
  gold: { borderColor: "rgba(196,152,42,0.6)" },
});
