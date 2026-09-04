import { useEffect, useRef } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";

import { colors, fonts, spacing } from "@/theme";

export function LoadingState({ label = "Running YWP protocol…" }: { label?: string }) {
  const spin = useRef(new Animated.Value(0)).current;
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const rotate = Animated.loop(
      Animated.timing(spin, {
        toValue: 1,
        duration: 1600,
        useNativeDriver: true,
      }),
    );
    const breathe = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 900,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 900,
          useNativeDriver: true,
        }),
      ]),
    );
    rotate.start();
    breathe.start();
    return () => {
      rotate.stop();
      breathe.stop();
    };
  }, [pulse, spin]);

  const rotate = spin.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });
  const scale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.92, 1.06],
  });

  return (
    <View style={styles.wrap}>
      <Animated.View style={[styles.ring, { transform: [{ rotate }, { scale }] }]} />
      <View style={styles.core} />
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: spacing.huge, alignItems: "center", gap: spacing.md },
  ring: {
    width: 54,
    height: 54,
    borderRadius: 27,
    borderWidth: 2,
    borderColor: colors.gold,
    borderTopColor: "transparent",
    borderRightColor: "rgba(240,193,74,0.25)",
  },
  core: {
    position: "absolute",
    top: spacing.huge + 17,
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.goldMute,
    borderWidth: 1,
    borderColor: colors.gold,
  },
  label: {
    color: colors.muted,
    fontFamily: fonts.bodyMedium,
    fontWeight: "600",
    letterSpacing: 0.3,
  },
});
