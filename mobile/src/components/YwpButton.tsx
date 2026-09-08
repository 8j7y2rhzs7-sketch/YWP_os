import { useEffect, useRef } from "react";
import {
  ActivityIndicator,
  Animated,
  Pressable,
  StyleSheet,
  Text,
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
  const sweep = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (variant !== "gold" || inactive) return;
    const loop = Animated.loop(
      Animated.timing(sweep, {
        toValue: 1,
        duration: 2800,
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [inactive, sweep, variant]);

  const sweepX = sweep.interpolate({
    inputRange: [0, 1],
    outputRange: [-140, 280],
  });

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
          <Animated.View
            pointerEvents="none"
            style={[styles.energy, { transform: [{ translateX: sweepX }] }]}
          >
            <LinearGradient
              colors={["transparent", "rgba(255,255,255,0.42)", "transparent"]}
              start={{ x: 0, y: 0.5 }}
              end={{ x: 1, y: 0.5 }}
              style={StyleSheet.absoluteFill}
            />
          </Animated.View>
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
    minHeight: touch.comfortable,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  energy: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: 64,
  },
  outline: { borderWidth: 1.5, borderColor: "rgba(196,152,42,0.55)" },
  danger: { borderColor: colors.danger },
  success: { borderColor: colors.success },
  goldText: {
    ...type.button,
    color: colors.background,
  },
  outlineText: {
    ...type.button,
    color: colors.white,
  },
  pressed: { transform: [{ scale: 0.985 }], opacity: 0.92 },
  disabled: { opacity: 0.45 },
});
