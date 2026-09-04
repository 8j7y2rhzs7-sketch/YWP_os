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
}

export function MetalPanel({
  children,
  style,
  tone = "default",
}: MetalPanelProps) {
  const palette =
    tone === "success"
      ? gradients.success
      : tone === "danger"
        ? gradients.danger
        : tone === "gold"
          ? gradients.panelGold
          : gradients.panel;
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
      <View style={styles.edge} />
      <View style={styles.highlight} />
      {children}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  panel: {
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.08)",
    padding: spacing.lg,
    gap: spacing.md,
    overflow: "hidden",
    ...shadow,
  },
  edge: {
    position: "absolute",
    left: 0,
    top: 14,
    bottom: 14,
    width: 2,
    borderRadius: 2,
    backgroundColor: colors.goldMute,
  },
  highlight: {
    position: "absolute",
    top: 0,
    left: 22,
    right: 22,
    height: StyleSheet.hairlineWidth,
    backgroundColor: "rgba(255,255,255,0.22)",
  },
  success: { borderColor: "rgba(63,219,150,0.45)" },
  danger: { borderColor: "rgba(255,101,119,0.45)" },
  gold: { borderColor: "rgba(196,152,42,0.55)" },
});
