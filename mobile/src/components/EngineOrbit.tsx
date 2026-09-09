import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  AccessibilityInfo,
  Animated,
  Easing,
  Image,
  StyleSheet,
  Text,
  View,
  type ImageSourcePropType,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import { brandAssets } from "@/brandAssets";
import { colors, fonts, spacing } from "@/theme";

type OrbitTone = "idle" | "loading" | "verified" | "partial" | "danger";

interface EngineOrbitProps {
  size?: number;
  tone?: OrbitTone;
  label?: string;
  source?: ImageSourcePropType;
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
}

const toneRing: Record<OrbitTone, string> = {
  idle: colors.circuitBlue,
  loading: colors.gold,
  verified: colors.success,
  partial: colors.warning,
  danger: colors.danger,
};

/**
 * Focal Decision Engine object: emblem + soft concentric rings.
 * Motion is calm and purposeful — breathe / settle, not noise.
 */
export function EngineOrbit({
  size = 220,
  tone = "idle",
  label,
  source = brandAssets.decisionEngineEmblem,
  children,
  style,
}: EngineOrbitProps) {
  const [reduceMotion, setReduceMotion] = useState(false);
  const breathe = useRef(new Animated.Value(0)).current;
  const spin = useRef(new Animated.Value(0)).current;
  const settle = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let alive = true;
    AccessibilityInfo.isReduceMotionEnabled().then((value) => {
      if (alive) setReduceMotion(value);
    });
    const sub = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      setReduceMotion,
    );
    return () => {
      alive = false;
      sub.remove();
    };
  }, []);

  useEffect(() => {
    settle.setValue(0);
    Animated.spring(settle, {
      toValue: 1,
      friction: 8,
      tension: 64,
      useNativeDriver: true,
    }).start();
  }, [settle, tone]);

  useEffect(() => {
    if (reduceMotion) {
      breathe.setValue(0.5);
      spin.setValue(0);
      return;
    }
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(breathe, {
          toValue: 1,
          duration: tone === "loading" ? 1100 : 3200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(breathe, {
          toValue: 0,
          duration: tone === "loading" ? 1100 : 3200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    pulse.start();

    let rotate: Animated.CompositeAnimation | null = null;
    if (tone === "loading") {
      spin.setValue(0);
      rotate = Animated.loop(
        Animated.timing(spin, {
          toValue: 1,
          duration: 9000,
          easing: Easing.linear,
          useNativeDriver: true,
        }),
      );
      rotate.start();
    } else {
      spin.setValue(0);
    }

    return () => {
      pulse.stop();
      rotate?.stop();
    };
  }, [breathe, reduceMotion, spin, tone]);

  const ringColor = toneRing[tone];
  const outer = size;
  const mid = size * 0.78;
  const inner = size * 0.58;
  const emblem = size * 0.42;

  const scale = breathe.interpolate({
    inputRange: [0, 1],
    outputRange: [1, tone === "loading" ? 1.045 : 1.028],
  });
  const ringOpacity = breathe.interpolate({
    inputRange: [0, 1],
    outputRange: [0.28, 0.72],
  });
  const rotate = spin.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  return (
    <Animated.View
      style={[
        styles.wrap,
        { width: outer, height: outer },
        style,
        {
          opacity: settle,
          transform: [
            {
              scale: settle.interpolate({
                inputRange: [0, 1],
                outputRange: [0.94, 1],
              }),
            },
          ],
        },
      ]}
    >
      <Animated.View
        pointerEvents="none"
        style={[
          styles.ring,
          {
            width: outer,
            height: outer,
            borderRadius: outer / 2,
            borderColor: ringColor,
            opacity: ringOpacity,
            transform: [{ scale }, { rotate }],
          },
        ]}
      />
      <Animated.View
        pointerEvents="none"
        style={[
          styles.ring,
          styles.ringDashed,
          {
            width: mid,
            height: mid,
            borderRadius: mid / 2,
            borderColor: colors.gold,
            opacity: ringOpacity,
            transform: [{ scale }],
          },
        ]}
      />
      <View
        pointerEvents="none"
        style={[
          styles.ring,
          {
            width: inner,
            height: inner,
            borderRadius: inner / 2,
            borderColor: "rgba(255,255,255,0.16)",
            opacity: 0.9,
          },
        ]}
      />
      <View style={[styles.coreGlow, { width: emblem + 28, height: emblem + 28, borderRadius: (emblem + 28) / 2 }]} />
      <Image
        source={source}
        style={{ width: emblem, height: emblem, borderRadius: emblem * 0.22 }}
        resizeMode="contain"
        accessibilityLabel="YWP Decision Engine"
      />
      {label ? <Text style={styles.label}>{label}</Text> : null}
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignSelf: "center",
    alignItems: "center",
    justifyContent: "center",
  },
  ring: {
    position: "absolute",
    borderWidth: StyleSheet.hairlineWidth * 2,
  },
  ringDashed: {
    borderStyle: "dashed",
  },
  coreGlow: {
    position: "absolute",
    backgroundColor: "rgba(26,168,240,0.14)",
    borderWidth: 1,
    borderColor: "rgba(240,193,74,0.28)",
  },
  label: {
    position: "absolute",
    bottom: -4,
    color: colors.goldBright,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.4,
    textTransform: "uppercase",
    backgroundColor: "rgba(2,5,10,0.82)",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    overflow: "hidden",
  },
});
