import { useEffect, useRef, type ReactNode } from "react";
import { Animated, Easing, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { useReduceMotion } from "@/hooks/useReduceMotion";

interface MetalShimmerProps {
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
  /** How often the glint repeats (ms). */
  periodMs?: number;
  intensity?: "soft" | "bright";
}

/**
 * Left→right metallic glint from the splash / logo reel.
 * Overlay on brand marks, CTAs, or thin chrome bars.
 */
export function MetalShimmer({
  children,
  style,
  periodMs = 2800,
  intensity = "soft",
}: MetalShimmerProps) {
  const reduceMotion = useReduceMotion();
  const sweep = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (reduceMotion) {
      sweep.setValue(0.35);
      return;
    }
    sweep.setValue(0);
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(sweep, {
          toValue: 1,
          duration: Math.max(900, periodMs - 700),
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.delay(700),
        Animated.timing(sweep, {
          toValue: 0,
          duration: 0,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [periodMs, reduceMotion, sweep]);

  const translateX = sweep.interpolate({
    inputRange: [0, 1],
    outputRange: [-120, 280],
  });
  const peak = intensity === "bright" ? 0.55 : 0.32;

  return (
    <View style={[styles.wrap, style]}>
      {children}
      <Animated.View
        pointerEvents="none"
        style={[styles.beam, { transform: [{ translateX }] }]}
      >
        <LinearGradient
          colors={[
            "transparent",
            `rgba(255,231,160,${peak})`,
            `rgba(255,255,255,${peak + 0.15})`,
            `rgba(72,196,255,${peak * 0.7})`,
            "transparent",
          ]}
          start={{ x: 0, y: 0.5 }}
          end={{ x: 1, y: 0.5 }}
          style={StyleSheet.absoluteFill}
        />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    overflow: "hidden",
    position: "relative",
  },
  beam: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: 72,
  },
});
