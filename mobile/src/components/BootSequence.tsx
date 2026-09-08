import { useEffect, useMemo, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Animated,
  Dimensions,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { brandAssets } from "@/brandAssets";
import { brand, colors, fonts, gradients, spacing } from "@/theme";

interface BootSequenceProps {
  ready: boolean;
  fontError?: Error | null;
  onDone: () => void;
}

const MIN_VISIBLE_MS = 2400;
const MAX_VISIBLE_MS = 4200;

/**
 * Full-screen Decision Engine entrance — emblem on stadium night,
 * slow fade/scale (no tiny landscape GIF).
 */
export function BootSequence({ ready, fontError, onDone }: BootSequenceProps) {
  const [reduceMotion, setReduceMotion] = useState(false);
  const opacity = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(0.88)).current;
  const glow = useRef(new Animated.Value(0)).current;
  const startedAt = useRef(Date.now());
  const finished = useRef(false);
  const { width: screenW, height: screenH } = Dimensions.get("window");
  const emblemSize = Math.min(screenW * 0.86, screenH * 0.52, 420);

  useEffect(() => {
    let alive = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((value) => {
        if (alive) setReduceMotion(value);
      })
      .catch(() => undefined);
    const sub = AccessibilityInfo.addEventListener?.(
      "reduceMotionChanged",
      setReduceMotion,
    );
    return () => {
      alive = false;
      sub?.remove?.();
    };
  }, []);

  useEffect(() => {
    if (reduceMotion) {
      opacity.setValue(1);
      scale.setValue(1);
      return;
    }
    Animated.parallel([
      Animated.timing(opacity, {
        toValue: 1,
        duration: 900,
        useNativeDriver: true,
      }),
      Animated.spring(scale, {
        toValue: 1,
        friction: 8,
        tension: 42,
        useNativeDriver: true,
      }),
    ]).start();
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(glow, {
          toValue: 1,
          duration: 1800,
          useNativeDriver: true,
        }),
        Animated.timing(glow, {
          toValue: 0,
          duration: 1800,
          useNativeDriver: true,
        }),
      ]),
    );
    pulse.start();
    return () => pulse.stop();
  }, [glow, opacity, reduceMotion, scale]);

  const finish = useMemo(
    () => () => {
      if (finished.current) return;
      finished.current = true;
      onDone();
    },
    [onDone],
  );

  useEffect(() => {
    const maxTimer = setTimeout(
      finish,
      reduceMotion ? MIN_VISIBLE_MS : MAX_VISIBLE_MS,
    );
    return () => clearTimeout(maxTimer);
  }, [finish, reduceMotion]);

  useEffect(() => {
    if (!ready) return;
    const elapsed = Date.now() - startedAt.current;
    const wait = Math.max(0, (reduceMotion ? 900 : MIN_VISIBLE_MS) - elapsed);
    const timer = setTimeout(finish, wait);
    return () => clearTimeout(timer);
  }, [finish, ready, reduceMotion]);

  const status = fontError
    ? "Continuing with system type"
    : ready
      ? "Decision Engine online"
      : "Initializing…";

  const glowOpacity = glow.interpolate({
    inputRange: [0, 1],
    outputRange: [0.25, 0.55],
  });

  return (
    <View style={styles.root} accessibilityLabel="YWP OS boot sequence">
      <LinearGradient colors={gradients.pageDeep} style={StyleSheet.absoluteFill} />
      <View style={styles.blueGlow} />
      <View style={styles.goldGlow} />

      <Animated.View
        style={[
          styles.stage,
          {
            opacity,
            transform: [{ scale }],
          },
        ]}
      >
        <Animated.View style={[styles.emblemAura, { opacity: glowOpacity, width: emblemSize + 48, height: emblemSize + 48 }]} />
        <Image
          source={brandAssets.decisionEngineEmblem}
          style={{ width: emblemSize, height: emblemSize }}
          resizeMode="contain"
          accessibilityLabel="YWP Decision Engine"
          accessibilityIgnoresInvertColors
        />
        <Text style={styles.product}>{brand.product}</Text>
        <Text style={styles.tagline}>{brand.tagline}</Text>
        <Text style={styles.status}>{status}</Text>
      </Animated.View>

      <Pressable
        onPress={finish}
        style={styles.skip}
        accessibilityRole="button"
        accessibilityLabel="Skip boot sequence"
      >
        <Text style={styles.skipText}>CONTINUE</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    alignItems: "center",
  },
  blueGlow: {
    position: "absolute",
    top: -80,
    left: -100,
    width: 340,
    height: 340,
    borderRadius: 170,
    backgroundColor: colors.circuitBlue,
    opacity: 0.28,
  },
  goldGlow: {
    position: "absolute",
    bottom: 80,
    right: -90,
    width: 300,
    height: 300,
    borderRadius: 150,
    backgroundColor: colors.gold,
    opacity: 0.16,
  },
  stage: {
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    width: "100%",
  },
  emblemAura: {
    position: "absolute",
    borderRadius: 999,
    backgroundColor: colors.circuitBlue,
    top: "12%",
  },
  product: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 36,
    fontWeight: "800",
    letterSpacing: 1,
    marginTop: spacing.md,
  },
  tagline: {
    color: colors.circuitBlueBright,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 2.6,
  },
  status: {
    color: colors.silver,
    fontFamily: fonts.bodyMedium,
    fontSize: 14,
    marginTop: spacing.sm,
    textAlign: "center",
  },
  skip: {
    position: "absolute",
    bottom: 48,
    alignSelf: "center",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
  },
  skipText: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.8,
  },
});
