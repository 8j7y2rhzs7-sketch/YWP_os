import { useEffect, useMemo, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Animated,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { brandAssets } from "@/brandAssets";
import { brand, colors, fonts, spacing } from "@/theme";

interface BootSequenceProps {
  ready: boolean;
  fontError?: Error | null;
  onDone: () => void;
}

const MIN_VISIBLE_MS = 2400;
const MAX_VISIBLE_MS = 4200;

/**
 * Full-screen entrance. The night board is the graphic:
 * one play has crossed the line, the lock is shut, the candle is still lit.
 */
export function BootSequence({ ready, fontError, onDone }: BootSequenceProps) {
  const [reduceMotion, setReduceMotion] = useState(false);
  const opacity = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(0.96)).current;
  const startedAt = useRef(Date.now());
  const finished = useRef(false);

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
  }, [opacity, reduceMotion, scale]);

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

  return (
    <View style={styles.root} accessibilityLabel="YWP OS boot sequence">
      <Image
        source={brandAssets.nightBoard}
        style={StyleSheet.absoluteFill}
        resizeMode="cover"
        accessibilityLabel="Night board. The play has crossed the line. The lock is shut. One candle is still lit."
        accessibilityIgnoresInvertColors
      />
      <LinearGradient
        colors={["transparent", "rgba(2,5,10,0.15)", "rgba(2,5,10,0.94)"]}
        locations={[0, 0.45, 1]}
        style={styles.scrim}
      />

      <Animated.View
        style={[
          styles.stage,
          {
            opacity,
            transform: [{ scale }],
          },
        ]}
      >
        <Text style={styles.product}>{brand.product}</Text>
        <Text style={styles.tagline} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.72}>
          ANALYZE · WEIGH · DECIDE · ADAPT · EXECUTE
        </Text>
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
    justifyContent: "flex-end",
    alignItems: "center",
  },
  scrim: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: "46%",
  },
  stage: {
    alignItems: "center",
    justifyContent: "flex-end",
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingBottom: 108,
    width: "100%",
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
    letterSpacing: 1.1,
    textAlign: "center",
    paddingHorizontal: spacing.lg,
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
