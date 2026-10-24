import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type ViewStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { colors, gradients, radius, spacing, touch, type } from "@/theme";

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
        <View style={[styles.inner, styles.gold]}>
          {loading ? (
            <ActivityIndicator color={colors.ink} />
          ) : (
            <Text style={styles.goldText}>{label}</Text>
          )}
        </View>
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
    minHeight: touch.comfortable,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  gold: { backgroundColor: colors.gold },
  outline: { borderWidth: 1, borderColor: colors.border },
  danger: { borderColor: colors.danger },
  success: { borderColor: colors.success },
  goldText: {
    ...type.button,
    color: colors.ink,
  },
  outlineText: {
    ...type.button,
    color: colors.white,
  },
  pressed: { transform: [{ scale: 0.985 }], opacity: 0.92 },
  disabled: { opacity: 0.45 },
});
