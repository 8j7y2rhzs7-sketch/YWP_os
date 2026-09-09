import { useEffect, useMemo, useRef } from "react";
import { Animated, Easing, StyleSheet, View } from "react-native";

import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors } from "@/theme";

interface SignalFieldProps {
  density?: "low" | "high";
  accent?: string;
  secondary?: string;
}

/**
 * Floating signal sparks — continuous drift + twinkle like reel particle systems.
 * Pure Views (no WebGL). Meant as atmosphere under hero stages.
 */
export function SignalField({
  density = "high",
  accent = colors.circuitBlueBright,
  secondary = colors.goldBright,
}: SignalFieldProps) {
  const reduceMotion = useReduceMotion();
  const count = density === "high" ? 18 : 10;
  const seeds = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        id: i,
        left: ((i * 47) % 100) + (i % 3) * 0.7,
        top: ((i * 29) % 88) + 4,
        size: 2 + (i % 4),
        color: i % 3 === 0 ? secondary : accent,
        duration: 3200 + (i % 7) * 700,
        delay: (i % 5) * 180,
      })),
    [accent, count, secondary],
  );
  const values = useRef(seeds.map(() => new Animated.Value(0))).current;

  useEffect(() => {
    while (values.length < seeds.length) values.push(new Animated.Value(0));
    if (reduceMotion) {
      for (const v of values) v.setValue(0.5);
      return;
    }
    const loops = seeds.map((seed, index) => {
      const v = values[index];
      if (!v) return null;
      v.setValue(0);
      const loop = Animated.loop(
        Animated.sequence([
          Animated.delay(seed.delay),
          Animated.timing(v, {
            toValue: 1,
            duration: seed.duration,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
          Animated.timing(v, {
            toValue: 0,
            duration: seed.duration,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
        ]),
      );
      loop.start();
      return loop;
    });
    return () => {
      for (const loop of loops) loop?.stop();
    };
  }, [reduceMotion, seeds, values]);

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      {seeds.map((seed, index) => {
        const v = values[index] ?? new Animated.Value(0.5);
        return (
          <Animated.View
            key={seed.id}
            style={{
              position: "absolute",
              left: `${seed.left}%`,
              top: `${seed.top}%`,
              width: seed.size,
              height: seed.size,
              borderRadius: seed.size,
              backgroundColor: seed.color,
              opacity: v.interpolate({
                inputRange: [0, 0.5, 1],
                outputRange: [0.05, 0.85, 0.1],
              }),
              transform: [
                {
                  translateY: v.interpolate({
                    inputRange: [0, 1],
                    outputRange: [18, -22],
                  }),
                },
                {
                  translateX: v.interpolate({
                    inputRange: [0, 1],
                    outputRange: [-6, 10],
                  }),
                },
                {
                  scale: v.interpolate({
                    inputRange: [0, 0.5, 1],
                    outputRange: [0.6, 1.35, 0.7],
                  }),
                },
              ],
              shadowColor: seed.color,
              shadowOpacity: 0.9,
              shadowRadius: 6,
              shadowOffset: { width: 0, height: 0 },
            }}
          />
        );
      })}
    </View>
  );
}
