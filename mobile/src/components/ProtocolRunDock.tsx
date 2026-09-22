import { useEffect, useRef } from "react";
import {
  ActivityIndicator,
  Animated,
  Easing,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors, fonts, gradients, radius, spacing, type } from "@/theme";

interface ProtocolRunDockProps {
  sport: string;
  playCount: number;
  readiness?: string;
  loading?: boolean;
  disabled?: boolean;
  onPress: () => void;
}

/**
 * Sticky launch rail — a stylus tip + ignition ring so RUN stays reachable
 * above long raw candidate lists without scrolling to the footer.
 */
export function ProtocolRunDock({
  sport,
  playCount,
  readiness,
  loading = false,
  disabled = false,
  onPress,
}: ProtocolRunDockProps) {
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const pulse = useRef(new Animated.Value(0)).current;
  const glide = useRef(new Animated.Value(0)).current;
  const enter = useRef(new Animated.Value(0)).current;
  const inactive = disabled || loading || playCount <= 0;

  useEffect(() => {
    Animated.spring(enter, {
      toValue: 1,
      friction: 7,
      tension: 64,
      useNativeDriver: true,
    }).start();
  }, [enter]);

  useEffect(() => {
    if (reduceMotion || inactive) {
      pulse.setValue(0.35);
      glide.setValue(0.5);
      return;
    }
    const ring = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 1100,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 1100,
          easing: Easing.in(Easing.quad),
          useNativeDriver: true,
        }),
      ]),
    );
    const stylus = Animated.loop(
      Animated.timing(glide, {
        toValue: 1,
        duration: 2400,
        easing: Easing.inOut(Easing.sin),
        useNativeDriver: true,
      }),
    );
    ring.start();
    stylus.start();
    return () => {
      ring.stop();
      stylus.stop();
    };
  }, [glide, inactive, pulse, reduceMotion]);

  const ringScale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.18],
  });
  const ringOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.55, 0.08],
  });
  const stylusY = glide.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [0, -5, 0],
  });

  const readyLabel =
    readiness === "VERIFIED"
      ? "VERIFIED"
      : readiness === "PARTIAL"
        ? "PARTIAL"
        : readiness === "DEMO"
          ? "DEMO"
          : "STANDBY";

  return (
    <Animated.View
      pointerEvents="box-none"
      style={[
        styles.wrap,
        {
          paddingBottom: Math.max(insets.bottom, 8) + 58,
          opacity: enter,
          transform: [
            {
              translateY: enter.interpolate({
                inputRange: [0, 1],
                outputRange: [28, 0],
              }),
            },
          ],
        },
      ]}
    >
      <LinearGradient
        colors={["rgba(2,5,10,0)", "rgba(2,5,10,0.82)", "rgba(2,5,10,0.96)"]}
        style={styles.fade}
        pointerEvents="none"
      />
      <View style={styles.railShell}>
        <LinearGradient colors={gradients.panelGold} style={styles.rail}>
          <View style={styles.railSheen} />
          <View style={styles.meta}>
            <Text style={styles.sport}>{sport.toUpperCase()}</Text>
            <Text style={styles.plays}>
              {playCount} PLAY{playCount === 1 ? "" : "S"}
            </Text>
            <Text style={styles.ready}>{readyLabel}</Text>
          </View>

          <View style={styles.stylusTrack} pointerEvents="none">
            <View style={styles.trackLine} />
            <Animated.View style={{ transform: [{ translateY: stylusY }] }}>
              <LinearGradient
                colors={["#FFE58D", "#E2AD26", "#8B5D08"]}
                style={styles.stylusBody}
              >
                <View style={styles.stylusTip} />
              </LinearGradient>
            </Animated.View>
          </View>

          <Pressable
            onPress={onPress}
            disabled={inactive}
            accessibilityRole="button"
            accessibilityLabel="Run AIN Strict Mode"
            style={({ pressed }) => [
              styles.ignitionHit,
              pressed && !inactive && styles.pressed,
              inactive && styles.disabled,
            ]}
          >
            <Animated.View
              style={[
                styles.pulseRing,
                {
                  opacity: ringOpacity,
                  transform: [{ scale: ringScale }],
                },
              ]}
            />
            <LinearGradient colors={gradients.gold} style={styles.ignition}>
              {loading ? (
                <ActivityIndicator color={colors.background} />
              ) : (
                <>
                  <Text style={styles.runEyebrow}>LAUNCH</Text>
                  <Text style={styles.runLabel}>RUN</Text>
                </>
              )}
            </LinearGradient>
          </Pressable>
        </LinearGradient>
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.lg,
    zIndex: 40,
  },
  fade: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: 120,
  },
  railShell: {
    borderRadius: radius.lg,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(240,193,74,0.45)",
    shadowColor: colors.gold,
    shadowOpacity: 0.28,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 6 },
    elevation: 12,
  },
  rail: {
    minHeight: 72,
    paddingVertical: spacing.sm,
    paddingLeft: spacing.lg,
    paddingRight: spacing.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  railSheen: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 1,
    backgroundColor: "rgba(255,229,141,0.35)",
  },
  meta: {
    flex: 1,
    gap: 2,
  },
  sport: {
    color: colors.goldBright,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    letterSpacing: 1.4,
  },
  plays: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 18,
    letterSpacing: -0.3,
  },
  ready: {
    ...type.caption,
    color: colors.silver,
    letterSpacing: 0.8,
  },
  stylusTrack: {
    width: 18,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  trackLine: {
    position: "absolute",
    width: 2,
    top: 4,
    bottom: 4,
    borderRadius: 1,
    backgroundColor: "rgba(240,193,74,0.28)",
  },
  stylusBody: {
    width: 10,
    height: 34,
    borderRadius: 5,
    alignItems: "center",
    paddingTop: 3,
  },
  stylusTip: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.background,
  },
  ignitionHit: {
    width: 72,
    height: 72,
    alignItems: "center",
    justifyContent: "center",
  },
  pulseRing: {
    position: "absolute",
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 2,
    borderColor: colors.goldBright,
  },
  ignition: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
  },
  runEyebrow: {
    color: colors.background,
    fontFamily: fonts.bodyBold,
    fontSize: 8,
    letterSpacing: 1.2,
    opacity: 0.75,
  },
  runLabel: {
    color: colors.background,
    fontFamily: fonts.display,
    fontSize: 16,
    letterSpacing: 0.6,
    marginTop: -1,
  },
  pressed: { transform: [{ scale: 0.96 }], opacity: 0.92 },
  disabled: { opacity: 0.45 },
});
