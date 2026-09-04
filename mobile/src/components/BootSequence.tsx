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

import { brandAssets } from "@/brandAssets";
import { brand, colors, fonts, spacing } from "@/theme";

interface BootSequenceProps {
  /** True once fonts loaded or failed — real init, not GIF artwork status. */
  ready: boolean;
  fontError?: Error | null;
  onDone: () => void;
}

const MIN_VISIBLE_MS = 700;
const MAX_VISIBLE_MS = 2200;

/**
 * Short branded entrance using the recovered boot GIF / engine still.
 * Baked-in GIF percentages are artwork only — labels come from real init state.
 */
export function BootSequence({ ready, fontError, onDone }: BootSequenceProps) {
  const [reduceMotion, setReduceMotion] = useState(false);
  const opacity = useRef(new Animated.Value(0)).current;
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
    Animated.timing(opacity, {
      toValue: 1,
      duration: reduceMotion ? 120 : 320,
      useNativeDriver: true,
    }).start();
  }, [opacity, reduceMotion]);

  const finish = useMemo(
    () => () => {
      if (finished.current) return;
      finished.current = true;
      onDone();
    },
    [onDone],
  );

  useEffect(() => {
    const maxTimer = setTimeout(finish, reduceMotion ? MIN_VISIBLE_MS : MAX_VISIBLE_MS);
    return () => clearTimeout(maxTimer);
  }, [finish, reduceMotion]);

  useEffect(() => {
    if (!ready) return;
    const elapsed = Date.now() - startedAt.current;
    const wait = Math.max(0, (reduceMotion ? 200 : MIN_VISIBLE_MS) - elapsed);
    const timer = setTimeout(finish, wait);
    return () => clearTimeout(timer);
  }, [finish, ready, reduceMotion]);

  const status = fontError
    ? "Fonts unavailable — continuing with system type"
    : ready
      ? "Systems ready"
      : "Loading type and session…";

  return (
    <View style={styles.root} accessibilityLabel="YWP OS boot sequence">
      <Animated.View style={[styles.stage, { opacity }]}>
        <Image
          source={reduceMotion ? brandAssets.bootFrame : brandAssets.bootSequence}
          style={styles.bootArt}
          resizeMode="contain"
          accessibilityIgnoresInvertColors
        />
        <View style={styles.badge}>
          <Image
            source={brandAssets.crest}
            style={styles.crest}
            resizeMode="contain"
            accessibilityLabel="YWP OS crown emblem"
          />
          <Text style={styles.product}>{brand.product}</Text>
          <Text style={styles.descriptor}>{brand.descriptor}</Text>
          <Text style={styles.status}>{status}</Text>
          <Text style={styles.note}>
            Boot art is brand reference — not live verification or progress.
          </Text>
        </View>
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
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl,
  },
  stage: { flex: 1, justifyContent: "center", gap: spacing.lg },
  bootArt: {
    width: "100%",
    height: 220,
    alignSelf: "center",
  },
  badge: {
    alignItems: "center",
    gap: spacing.sm,
  },
  crest: { width: 88, height: 88, borderRadius: 44 },
  product: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: 3,
  },
  descriptor: {
    color: colors.silver,
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  status: {
    color: colors.white,
    fontFamily: fonts.bodyBold,
    fontSize: 14,
    fontWeight: "700",
    marginTop: spacing.sm,
    textAlign: "center",
  },
  note: {
    color: colors.dim,
    fontFamily: fonts.body,
    fontSize: 11,
    textAlign: "center",
    maxWidth: 320,
    lineHeight: 15,
  },
  skip: {
    alignSelf: "center",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
  },
  skipText: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.6,
  },
});
