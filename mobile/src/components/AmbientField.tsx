import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { colors, gradients } from "@/theme";

/** Stadium-night atmosphere with a slow broadcast scan beam. */
export function AmbientField({
  sportAccent,
  pageColors,
}: {
  sportAccent?: string;
  pageColors?: readonly [string, string, string];
}) {
  const pulse = useRef(new Animated.Value(0)).current;
  const scan = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const breathe = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 4800,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 4800,
          useNativeDriver: true,
        }),
      ]),
    );
    const beam = Animated.loop(
      Animated.timing(scan, {
        toValue: 1,
        duration: 5600,
        useNativeDriver: true,
      }),
    );
    breathe.start();
    beam.start();
    return () => {
      breathe.stop();
      beam.stop();
    };
  }, [pulse, scan]);

  const scale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.1],
  });
  const opacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.28, 0.5],
  });
  const scanY = scan.interpolate({
    inputRange: [0, 1],
    outputRange: [-80, 720],
  });

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <LinearGradient
        colors={pageColors ?? gradients.pageDeep}
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
      <View style={[styles.fieldWash, { backgroundColor: sportAccent ?? colors.gold }]} />
      <Animated.View style={[styles.scanWrap, { transform: [{ translateY: scanY }] }]}>
        <LinearGradient colors={gradients.scan} start={{ x: 0, y: 0.5 }} end={{ x: 1, y: 0.5 }} style={styles.scan} />
      </Animated.View>
      <LinearGradient
        colors={["transparent", "rgba(2,4,6,0.45)", "rgba(2,4,6,0.94)"]}
        style={styles.vignette}
      />
      <View style={styles.grain} />
    </View>
  );
}

const styles = StyleSheet.create({
  orbA: {
    position: "absolute",
    top: -100,
    right: -70,
    width: 300,
    height: 300,
    borderRadius: 150,
  },
  orbB: {
    position: "absolute",
    bottom: 100,
    left: -110,
    width: 260,
    height: 260,
    borderRadius: 130,
    opacity: 0.14,
  },
  fieldWash: {
    position: "absolute",
    left: 0,
    right: 0,
    top: "38%",
    height: 180,
    opacity: 0.05,
  },
  scanWrap: {
    position: "absolute",
    left: 0,
    right: 0,
    height: 48,
  },
  scan: {
    flex: 1,
    opacity: 0.55,
  },
  vignette: {
    ...StyleSheet.absoluteFill,
  },
  grain: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(255,255,255,0.018)",
  },
});
