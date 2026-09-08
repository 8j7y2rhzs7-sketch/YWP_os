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

import { colors, fonts, gradients, radius, spacing } from "@/theme";

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
        duration: 2400,
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
              colors={["transparent", "rgba(255,255,255,0.55)", "transparent"]}
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
    minHeight: 52,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  energy: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: 70,
  },
  outline: { borderWidth: 1, borderColor: colors.borderGold },
  danger: { borderColor: colors.danger },
  success: { borderColor: colors.success },
  goldText: {
    color: colors.background,
    fontFamily: fonts.displaySemi,
    fontWeight: "700",
    letterSpacing: 1.1,
    fontSize: 14,
  },
  outlineText: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontWeight: "700",
    letterSpacing: 0.8,
    fontSize: 14,
  },
  pressed: { transform: [{ scale: 0.97 }], opacity: 0.94 },
  disabled: { opacity: 0.5 },
});
