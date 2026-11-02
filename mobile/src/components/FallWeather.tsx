import { useEffect, useRef } from "react";
import { Animated, Dimensions, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { useReduceMotion } from "@/hooks/useReduceMotion";

const { height: SCREEN_H } = Dimensions.get("window");

const LEAVES = [
  { left: "4%", delay: 0, duration: 8200, size: 16, color: "#C45C26", drift: 28, tilt: -24 },
  { left: "12%", delay: 1400, duration: 10400, size: 11, color: "#E08A2E", drift: -22, tilt: 18 },
  { left: "22%", delay: 600, duration: 9100, size: 18, color: "#8C3B22", drift: 36, tilt: 32 },
  { left: "31%", delay: 2200, duration: 7600, size: 13, color: "#D4A04A", drift: -18, tilt: -12 },
  { left: "41%", delay: 900, duration: 11200, size: 15, color: "#B5522A", drift: 20, tilt: 40 },
  { left: "52%", delay: 2800, duration: 8800, size: 12, color: "#E6C27A", drift: -30, tilt: -36 },
  { left: "63%", delay: 400, duration: 9800, size: 17, color: "#A33B1A", drift: 26, tilt: 14 },
  { left: "72%", delay: 1800, duration: 8400, size: 10, color: "#C47A32", drift: -16, tilt: -28 },
  { left: "81%", delay: 3200, duration: 10800, size: 16, color: "#7A4A28", drift: 32, tilt: 22 },
  { left: "90%", delay: 1100, duration: 7900, size: 14, color: "#E07A1C", drift: -24, tilt: -8 },
  { left: "17%", delay: 3600, duration: 12000, size: 9, color: "#F0C14A", drift: 14, tilt: 48 },
  { left: "58%", delay: 2400, duration: 9300, size: 19, color: "#9A3412", drift: -28, tilt: -42 },
] as const;

function Leaf({
  spec,
  reduceMotion,
}: {
  spec: (typeof LEAVES)[number];
  reduceMotion: boolean;
}) {
  const fall = useRef(new Animated.Value(reduceMotion ? 0.35 : 0)).current;
  const sway = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (reduceMotion) return;
    const drop = Animated.loop(
      Animated.sequence([
        Animated.delay(spec.delay),
        Animated.timing(fall, {
          toValue: 1,
          duration: spec.duration,
          useNativeDriver: true,
        }),
        Animated.timing(fall, { toValue: 0, duration: 0, useNativeDriver: true }),
      ]),
    );
    const rock = Animated.loop(
      Animated.sequence([
        Animated.timing(sway, { toValue: 1, duration: 1800, useNativeDriver: true }),
        Animated.timing(sway, { toValue: 0, duration: 1800, useNativeDriver: true }),
      ]),
    );
    drop.start();
    rock.start();
    return () => {
      drop.stop();
      rock.stop();
    };
  }, [fall, reduceMotion, spec.delay, spec.duration, sway]);

  const translateY = fall.interpolate({
    inputRange: [0, 1],
    outputRange: [-40, SCREEN_H + 40],
  });
  const translateX = sway.interpolate({
    inputRange: [0, 1],
    outputRange: [-spec.drift, spec.drift],
  });
  const rotate = sway.interpolate({
    inputRange: [0, 1],
    outputRange: [`${spec.tilt - 20}deg`, `${spec.tilt + 24}deg`],
  });

  return (
    <Animated.View
      style={[
        styles.leaf,
        {
          left: spec.left,
          width: spec.size,
          height: spec.size * 1.35,
          backgroundColor: spec.color,
          borderTopLeftRadius: spec.size,
          borderTopRightRadius: spec.size * 0.35,
          borderBottomRightRadius: spec.size,
          borderBottomLeftRadius: spec.size * 0.25,
          transform: [{ translateY }, { translateX }, { rotate }],
        },
      ]}
    />
  );
}

/**
 * Fall over the glass. Leaves keep coming down.
 * A cold front frosts the screen until the forge has enough heat to melt it.
 */
export function FallWeather({
  heat = 0,
  thawed = false,
}: {
  /** 0 cold, 1 forge-hot. */
  heat?: number;
  thawed?: boolean;
}) {
  const reduceMotion = useReduceMotion();
  const frost = useRef(new Animated.Value(thawed ? 0.08 : 0.62)).current;
  const glow = useRef(new Animated.Value(thawed ? 0.7 : heat * 0.25)).current;

  useEffect(() => {
    const frostTo = thawed ? 0.05 : Math.max(0.18, 0.72 - heat * 0.45);
    const glowTo = thawed ? 0.85 : 0.12 + heat * 0.45;
    if (reduceMotion) {
      frost.setValue(frostTo);
      glow.setValue(glowTo);
      return;
    }
    Animated.parallel([
      Animated.timing(frost, { toValue: frostTo, duration: thawed ? 1600 : 700, useNativeDriver: true }),
      Animated.timing(glow, { toValue: glowTo, duration: thawed ? 1800 : 700, useNativeDriver: true }),
    ]).start();
  }, [frost, glow, heat, reduceMotion, thawed]);

  return (
    <View style={StyleSheet.absoluteFill} accessibilityElementsHidden>
      {LEAVES.map((spec) => (
        <Leaf key={`${spec.left}-${spec.delay}`} spec={spec} reduceMotion={reduceMotion} />
      ))}
      <Animated.View style={[StyleSheet.absoluteFill, { opacity: frost }]}>
        <LinearGradient
          colors={["rgba(210,232,255,0.55)", "rgba(150,190,220,0.28)", "rgba(8,16,28,0.05)"]}
          style={StyleSheet.absoluteFill}
        />
        <View style={styles.iceLine} />
        <View style={[styles.iceLine, styles.iceLineMid]} />
      </Animated.View>
      <Animated.View style={[styles.heat, { opacity: glow }]} pointerEvents="none">
        <LinearGradient
          colors={["rgba(255,120,20,0)", "rgba(255,90,20,0.08)", "rgba(255,70,16,0.55)"]}
          style={StyleSheet.absoluteFill}
        />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  leaf: {
    position: "absolute",
    top: 0,
  },
  iceLine: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 72,
    height: 1,
    backgroundColor: "rgba(255,255,255,0.55)",
  },
  iceLineMid: { top: 180, opacity: 0.45 },
  heat: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    height: "48%",
  },
});
