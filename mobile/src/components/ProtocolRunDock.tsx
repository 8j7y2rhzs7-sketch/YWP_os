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
  /** True when research is done and LAUNCH may grade. */
  armed?: boolean;
  loading?: boolean;
  disabled?: boolean;
  statusText?: string | null;
  onPress: () => void;
}

/**
 * Sticky launch rail — a stylus tip + ignition ring so RUN stays reachable
 * above long raw candidate lists without scrolling to the footer.
 *
 * Circuit-blue while research warms; gold only when armed to grade.
 */
export function ProtocolRunDock({
  sport,
  playCount,
  readiness,
  armed = true,
  loading = false,
  disabled = false,
  statusText = null,
  onPress,
}: ProtocolRunDockProps) {
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const pulse = useRef(new Animated.Value(0)).current;
  const glide = useRef(new Animated.Value(0)).current;
  const enter = useRef(new Animated.Value(0)).current;
  const inactive = disabled || playCount <= 0;
  const canPress = !inactive && !loading;
  const live = armed && !loading && !inactive;

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
          duration: armed ? 1100 : 900,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: armed ? 1100 : 900,
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
  }, [armed, glide, inactive, pulse, reduceMotion]);

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
    loading && !armed
      ? "WARMING"
      : !armed
        ? "WARMING"
        : readiness === "VERIFIED"
          ? "VERIFIED"
          : readiness === "PARTIAL"
            ? "PARTIAL"
            : readiness === "DEMO"
              ? "DEMO"
              : "ARMED";

  const railColors = armed ? gradients.panelGold : gradients.panelBlue;
  const stylusColors = armed
    ? (["#FFE58D", "#E2AD26", "#8B5D08"] as const)
    : ([colors.circuitBlueBright, colors.circuitBlue, colors.circuitBlueDeep] as const);
  const ignitionColors = armed
    ? gradients.gold
    : ([colors.circuitBlueBright, colors.circuitBlue, colors.circuitBlueDeep] as const);
  const ringBorder = armed ? colors.goldBright : colors.circuitBlueBright;
  const shellBorder = armed ? "rgba(240,193,74,0.45)" : "rgba(26,168,240,0.45)";
  const shadow = armed ? colors.gold : colors.circuitBlue;

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
      <View
        style={[
          styles.railShell,
          { borderColor: shellBorder, shadowColor: shadow },
        ]}
      >
        <LinearGradient colors={railColors} style={styles.rail}>
          <View style={styles.railSheen} />
          <View style={styles.meta}>
            <Text style={styles.sport}>{sport.toUpperCase()}</Text>
            <Text style={styles.plays}>
              {playCount} PLAY{playCount === 1 ? "" : "S"}
            </Text>
            <Text style={[styles.ready, !armed && styles.readyWarming]}>
              {readyLabel}
            </Text>
          </View>

          <View style={styles.stylusTrack} pointerEvents="none">
            <View
              style={[
                styles.trackLine,
                !armed && { backgroundColor: "rgba(26,168,240,0.35)" },
              ]}
            />
            <Animated.View style={{ transform: [{ translateY: stylusY }] }}>
              <LinearGradient colors={[...stylusColors]} style={styles.stylusBody}>
                <View
                  style={[
                    styles.stylusTip,
                    !armed && { backgroundColor: colors.circuitBlueBright },
                  ]}
                />
              </LinearGradient>
            </Animated.View>
          </View>

          <Pressable
            onPress={onPress}
            disabled={!canPress}
            accessibilityRole="button"
            accessibilityLabel={
              armed
                ? "Launch AIN Strict Mode"
                : "Research still warming — wait for gold"
            }
            style={({ pressed }) => [
              styles.ignitionHit,
              pressed && canPress && styles.pressed,
              (!canPress || !live) && !loading && styles.disabled,
            ]}
          >
            <Animated.View
              style={[
                styles.pulseRing,
                {
                  borderColor: ringBorder,
                  opacity: ringOpacity,
                  transform: [{ scale: ringScale }],
                },
              ]}
            />
            <LinearGradient colors={[...ignitionColors]} style={styles.ignition}>
              {loading ? (
                <>
                  <ActivityIndicator color={colors.background} />
                  {statusText ? (
                    <Text style={styles.runEyebrow} numberOfLines={1}>
                      {statusText}
                    </Text>
                  ) : null}
                </>
              ) : armed ? (
                <>
                  <Text style={styles.runEyebrow}>LAUNCH</Text>
                  <Text style={styles.runLabel}>RUN</Text>
                </>
              ) : (
                <>
                  <Text style={styles.runEyebrow}>WAIT</Text>
                  <Text style={styles.runLabel}>WARM</Text>
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
    shadowOpacity: 0.28,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 10,
  },
  rail: {
    minHeight: 78,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  railSheen: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(255,255,255,0.03)",
  },
  meta: {
    flex: 1,
    gap: 2,
  },
  sport: {
    ...type.eyebrow,
    color: colors.textMuted,
  },
  plays: {
    fontFamily: fonts.display,
    fontSize: 18,
    color: colors.text,
    letterSpacing: 0.4,
  },
  ready: {
    fontFamily: fonts.bodyBold,
    fontSize: 10,
    letterSpacing: 1.4,
    color: colors.gold,
  },
  readyWarming: {
    color: colors.circuitBlueBright,
  },
  stylusTrack: {
    width: 28,
    height: 52,
    alignItems: "center",
    justifyContent: "center",
  },
  trackLine: {
    position: "absolute",
    width: 2,
    height: 44,
    borderRadius: 1,
    backgroundColor: "rgba(240,193,74,0.28)",
  },
  stylusBody: {
    width: 10,
    height: 36,
    borderRadius: 5,
    alignItems: "center",
    paddingTop: 2,
  },
  stylusTip: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.goldBright,
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
