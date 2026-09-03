import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  type ViewStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { colors, gradients, radius, spacing } from "@/theme";

interface YwpButtonProps {
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: "gold" | "outline" | "danger" | "success";
  style?: ViewStyle;
}

export function YwpButton({
  label,
  onPress,
  loading = false,
  disabled = false,
  variant = "gold",
  style,
}: YwpButtonProps) {
  const inactive = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [
        styles.pressable,
        pressed && !inactive && styles.pressed,
        inactive && styles.disabled,
        style,
      ]}
    >
      {variant === "gold" ? (
        <LinearGradient colors={gradients.gold} style={styles.inner}>
          {loading ? (
            <ActivityIndicator color={colors.background} />
          ) : (
            <Text style={styles.goldText}>{label}</Text>
          )}
        </LinearGradient>
      ) : (
        <LinearGradient
          colors={
            variant === "danger"
              ? gradients.danger
              : variant === "success"
                ? gradients.success
                : (["#151B23", "#0A0D12"] as const)
          }
          style={[
            styles.inner,
            styles.outline,
            variant === "danger" && styles.danger,
            variant === "success" && styles.success,
          ]}
        >
          {loading ? (
            <ActivityIndicator color={colors.gold} />
          ) : (
            <Text style={styles.outlineText}>{label}</Text>
          )}
        </LinearGradient>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pressable: { borderRadius: radius.md, overflow: "hidden" },
  inner: {
    minHeight: 50,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: "center",
    justifyContent: "center",
  },
  outline: { borderWidth: 1, borderColor: colors.borderGold },
  danger: { borderColor: colors.danger },
  success: { borderColor: colors.success },
  goldText: {
    color: colors.background,
    fontWeight: "900",
    letterSpacing: 0.8,
    fontSize: 14,
  },
  outlineText: {
    color: colors.white,
    fontWeight: "900",
    letterSpacing: 0.6,
    fontSize: 14,
  },
  pressed: { transform: [{ scale: 0.985 }], opacity: 0.92 },
  disabled: { opacity: 0.5 },
});
