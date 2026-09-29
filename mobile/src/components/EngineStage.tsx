import { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { EngineCallouts } from "@/components/EngineCallouts";
import { EngineOrbit, type OrbitTone } from "@/components/EngineOrbit";
import { RippleGrid } from "@/components/RippleGrid";
import { SignalField } from "@/components/SignalField";
import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors } from "@/theme";

interface EngineStageProps {
  tone?: OrbitTone;
  label?: string;
  intensity?: "standard" | "hero";
  size?: number;
  style?: StyleProp<ViewStyle>;
  callouts?: { id: string; label: string; side: "left" | "right"; top: number }[];
  calloutsActive?: boolean;
}

/**
 * Full motion stage: signal sparks + radial ripple floor + engine orbit + callouts.
 */
export function EngineStage({
  tone = "idle",
  label,
  intensity = "standard",
  size = 220,
  style,
  callouts,
  calloutsActive = false,
}: EngineStageProps) {
  const reduceMotion = useReduceMotion();
  const scan = useRef(new Animated.Value(0)).current;
  const tilt = useRef(new Animated.Value(0)).current;
  const hero = intensity === "hero";
  const urgent = tone === "loading";
  const accent =
    tone === "verified"
      ? colors.success
      : tone === "loading"
        ? colors.gold
        : tone === "partial"
          ? colors.warning
          : tone === "danger"
            ? colors.danger
            : colors.circuitBlue;

  useEffect(() => {
    if (reduceMotion) {
      scan.setValue(0.4);
      tilt.setValue(0.5);
      return;
    }
    const beam = Animated.loop(
      Animated.timing(scan, {
        toValue: 1,
        duration: urgent ? 1600 : 3800,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    const sway = Animated.loop(
      Animated.sequence([
        Animated.timing(tilt, {
          toValue: 1,
          duration: 4200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(tilt, {
          toValue: 0,
          duration: 4200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    beam.start();
    sway.start();
    return () => {
      beam.stop();
      sway.stop();
    };
  }, [reduceMotion, scan, tilt, urgent]);

  const scanX = scan.interpolate({
    inputRange: [0, 1],
    outputRange: [-48, 300],
  });
  const stageTilt = tilt.interpolate({
    inputRange: [0, 1],
    outputRange: ["-1.8deg", "1.8deg"],
  });

  return (
    <View style={[styles.stage, hero && styles.stageHero, style]}>
      <SignalField
        density={hero ? "high" : "low"}
        accent={accent}
        secondary={colors.goldBright}
      />

      <View style={[styles.floorWrap, hero && styles.floorHero]} pointerEvents="none">
        <Animated.View
          style={[
            styles.floorPerspective,
            {
              transform: [
                { perspective: 520 },
                { rotateX: "62deg" },
                { rotateZ: stageTilt },
                { scale: 1.22 },
              ],
            },
          ]}
        >
          <RippleGrid
            rows={hero ? 7 : 5}
            cols={hero ? 9 : 7}
            active
            urgent={urgent}
            accent={accent}
          />
          <Animated.View style={[styles.scanBeam, { transform: [{ translateX: scanX }] }]}>
            <LinearGradient
              colors={[
                "transparent",
                `${accent}66`,
                "rgba(240,193,74,0.45)",
                "transparent",
              ]}
              start={{ x: 0, y: 0.5 }}
              end={{ x: 1, y: 0.5 }}
              style={StyleSheet.absoluteFill}
            />
          </Animated.View>
          <LinearGradient
            colors={["transparent", "rgba(2,5,10,0.35)", "rgba(2,5,10,0.96)"]}
            style={styles.floorFade}
          />
        </Animated.View>
      </View>

      <Animated.View
        style={[
          styles.orbitWrap,
          {
            transform: [
              {
                translateY: tilt.interpolate({
                  inputRange: [0, 1],
                  outputRange: [4, -6],
                }),
              },
              { rotateZ: stageTilt },
            ],
          },
        ]}
      >
        {callouts?.length ? (
          <EngineCallouts
            active={calloutsActive}
            accent={
              tone === "verified"
                ? colors.success
                : tone === "loading"
                  ? colors.goldBright
                  : colors.circuitBlueBright
            }
            items={callouts}
          />
        ) : null}
        <EngineOrbit size={size} tone={tone} label={label} intensity={intensity} />
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  stage: {
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    paddingBottom: 8,
    minHeight: 240,
    overflow: "visible",
  },
  stageHero: {
    minHeight: 320,
    paddingBottom: 16,
  },
  floorWrap: {
    position: "absolute",
    bottom: 0,
    left: 4,
    right: 4,
    height: 110,
    overflow: "hidden",
    borderRadius: 18,
  },
  floorHero: {
    height: 140,
  },
  floorPerspective: {
    flex: 1,
  },
  scanBeam: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: 64,
  },
  floorFade: {
    ...StyleSheet.absoluteFill,
  },
  orbitWrap: {
    width: "100%",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 220,
  },
});
