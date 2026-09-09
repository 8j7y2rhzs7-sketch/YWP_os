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
    outputRange: [1, 1.22],
  });
  const blueOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.28, 0.58],
  });
  const goldOpacity = pulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.2, 0.48],
  });
  const scanY = scan.interpolate({
    inputRange: [0, 1],
    outputRange: [-120, 820],
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
      <Animated.View
        style={[
          styles.scanWrap,
          styles.scanWrapAlt,
          {
            transform: [
              {
                translateY: scan.interpolate({
                  inputRange: [0, 1],
                  outputRange: [640, -100],
                }),
              },
            ],
          },
        ]}
      >
        <LinearGradient
          colors={["rgba(240,193,74,0)", "rgba(240,193,74,0.28)", "rgba(26,168,240,0)", "transparent"]}
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
    top: -90,
    left: -120,
    width: 380,
    height: 380,
    borderRadius: 190,
    backgroundColor: colors.circuitBlue,
  },
  orbGold: {
    position: "absolute",
    top: -100,
    right: -90,
    width: 340,
    height: 340,
    borderRadius: 170,
  },
  blueWash: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    width: "55%",
    backgroundColor: colors.circuitBlue,
    opacity: 0.14,
  },
  fieldWash: {
    position: "absolute",
    left: 0,
    right: 0,
    top: "32%",
    height: 220,
    opacity: 0.08,
  },
  scanWrap: {
    position: "absolute",
    left: 0,
    right: 0,
    height: 56,
  },
  scanWrapAlt: {
    opacity: 0.7,
  },
  scan: {
    flex: 1,
    opacity: 0.42,
  },
  vignette: {
    ...StyleSheet.absoluteFill,
  },
  grain: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(255,255,255,0.014)",
  },
});
