import { useEffect, useRef, type ReactNode } from "react";
import {
  Animated,
  Easing,
  StyleSheet,
  type StyleProp,
  View,
  type ViewStyle,
} from "react-native";

import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors, radius, spacing } from "@/theme";

interface MetalPanelProps {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  tone?: "default" | "success" | "danger" | "gold";
  accent?: string;
  /** Stagger entrance when many panels mount together. */
  motionDelay?: number;
  /** Soft enter animation (on by default for whole-app motion). */
  animate?: boolean;
}

export function MetalPanel({
  children,
  style,
  tone = "default",
  accent,
  motionDelay = 0,
  animate = true,
}: MetalPanelProps) {
  const reduceMotion = useReduceMotion();
  const enter = useRef(new Animated.Value(animate && !reduceMotion ? 0 : 1)).current;

  useEffect(() => {
    if (!animate || reduceMotion) {
      enter.setValue(1);
      return;
    }
    enter.setValue(0);
    const anim = Animated.timing(enter, {
      toValue: 1,
      duration: 420,
      delay: motionDelay,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    });
    anim.start();
    return () => anim.stop();
  }, [animate, enter, motionDelay, reduceMotion, tone]);

  const body = (
    <View
      style={[
        styles.panel,
        tone === "success" && styles.success,
        tone === "danger" && styles.danger,
        tone === "gold" && styles.gold,
        accent ? { borderColor: accent } : null,
        style,
      ]}
    >
      {children}
    </View>
  );

  if (!animate) return body;

  return (
    <Animated.View
      style={{
        opacity: enter,
        transform: [
          {
            translateY: enter.interpolate({
              inputRange: [0, 1],
              outputRange: [14, 0],
            }),
          },
        ],
      }}
    >
      {body}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  panel: {
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    padding: spacing.lg,
    gap: spacing.md,
    overflow: "hidden",
  },
  success: {
    backgroundColor: colors.successDeep,
    borderColor: "rgba(46,229,154,0.35)",
  },
  danger: {
    backgroundColor: colors.dangerDeep,
    borderColor: "rgba(255,77,106,0.35)",
  },
  gold: {
    backgroundColor: colors.surfaceRaised,
    borderColor: colors.border,
  },
});
