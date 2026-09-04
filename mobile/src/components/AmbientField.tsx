import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { colors, gradients } from "@/theme";

/** Soft gold/field atmosphere behind every screen. */
export function AmbientField({ sportAccent }: { sportAccent?: string }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 4200,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 4200,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  const scale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.08],
  });
  const opacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.35, 0.55],
  });

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <LinearGradient
        colors={gradients.pageDeep}
        style={StyleSheet.absoluteFill}
      />
      <Animated.View
        style={[
          styles.orbA,
          {
            backgroundColor: sportAccent ?? colors.gold,
            opacity,
            transform: [{ scale }],
          },
        ]}
      />
      <View style={[styles.orbB, { backgroundColor: sportAccent ?? colors.gold }]} />
      <LinearGradient
        colors={["transparent", "rgba(4,5,6,0.55)", "rgba(4,5,6,0.92)"]}
        style={styles.vignette}
      />
      <View style={styles.grain} />
    </View>
  );
}

const styles = StyleSheet.create({
  orbA: {
    position: "absolute",
    top: -80,
    right: -60,
    width: 260,
    height: 260,
    borderRadius: 130,
    opacity: 0.22,
  },
  orbB: {
    position: "absolute",
    bottom: 120,
    left: -90,
    width: 220,
    height: 220,
    borderRadius: 110,
    opacity: 0.12,
  },
  vignette: {
    ...StyleSheet.absoluteFill,
  },
  grain: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(255,255,255,0.015)",
  },
});
