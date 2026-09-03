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
          ? (["#2D2108", "#120F08", "#090B0F"] as const)
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
      <View style={styles.highlight} />
      {children}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  panel: {
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    gap: spacing.md,
    overflow: "hidden",
    ...shadow,
  },
  highlight: {
    position: "absolute",
    top: 0,
    left: 18,
    right: 18,
    height: 1,
    backgroundColor: "rgba(255,255,255,0.14)",
  },
  success: { borderColor: colors.success },
  danger: { borderColor: colors.danger },
  gold: { borderColor: colors.borderGold },
});
