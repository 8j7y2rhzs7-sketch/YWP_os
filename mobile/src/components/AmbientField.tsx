import { useEffect, useRef, useState } from "react";
import { AccessibilityInfo, Animated, StyleSheet, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { colors, gradients } from "@/theme";

/** Stadium night: circuit-blue left + gold right — matches the Decision Engine logo split. */
export function AmbientField({
  sportAccent,
  pageColors,
}: {
  sportAccent?: string;
  pageColors?: readonly [string, string, string];
}) {
  const [reduceMotion, setReduceMotion] = useState(false);
  const pulse = useRef(new Animated.Value(0)).current;
  const scan = useRef(new Animated.Value(0)).current;

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
    if (reduceMotion) {
      pulse.setValue(0.45);
      scan.setValue(0.35);
      return;
    }
    const breathe = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 5200,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 5200,
          useNativeDriver: true,
        }),
      ]),
    );
    const beam = Animated.loop(
      Animated.timing(scan, {
        toValue: 1,
        duration: 7800,
        useNativeDriver: true,
      }),
    );
    breathe.start();
    beam.start();
    return () => {
      breathe.stop();
      beam.stop();
    };
  }, [pulse, reduceMotion, scan]);

  const scale = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.12],
  });
  const blueOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.22, 0.42],
  });
  const goldOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.14, 0.3],
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
      {/* Circuit-blue orb — logo cybernetic half */}
      <Animated.View
        style={[
          styles.orbBlue,
          {
            opacity: blueOpacity,
            transform: [{ scale }],
          },
        ]}
      />
      {/* Gold orb — logo gear half / sport override */}
      <Animated.View
        style={[
          styles.orbGold,
          {
            backgroundColor: sportAccent ?? colors.gold,
            opacity: goldOpacity,
            transform: [{ scale }],
          },
        ]}
      />
      <View style={styles.blueWash} />
      <View style={[styles.fieldWash, { backgroundColor: sportAccent ?? colors.gold }]} />
      <Animated.View style={[styles.scanWrap, { transform: [{ translateY: scanY }] }]}>
        <LinearGradient
          colors={gradients.scan}
          start={{ x: 0, y: 0.5 }}
          end={{ x: 1, y: 0.5 }}
          style={styles.scan}
        />
      </Animated.View>
      <LinearGradient
        colors={["transparent", "rgba(2,5,10,0.42)", "rgba(2,5,10,0.94)"]}
        style={styles.vignette}
      />
      <View style={styles.grain} />
    </View>
  );
}

const styles = StyleSheet.create({
  orbBlue: {
    position: "absolute",
    top: -60,
    left: -90,
    width: 320,
    height: 320,
    borderRadius: 160,
    backgroundColor: colors.circuitBlue,
  },
  orbGold: {
    position: "absolute",
    top: -80,
    right: -70,
    width: 280,
    height: 280,
    borderRadius: 140,
  },
  blueWash: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    width: "52%",
    backgroundColor: colors.circuitBlue,
    opacity: 0.1,
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
    height: 40,
  },
  scan: {
    flex: 1,
    opacity: 0.28,
  },
  vignette: {
    ...StyleSheet.absoluteFill,
  },
  grain: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(255,255,255,0.014)",
  },
});
