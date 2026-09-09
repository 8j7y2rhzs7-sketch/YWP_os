import { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { EngineCallouts } from "@/components/EngineCallouts";
import { EngineOrbit, type OrbitTone } from "@/components/EngineOrbit";
import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors } from "@/theme";

interface EngineStageProps {
  tone?: OrbitTone;
  label?: string;
  intensity?: "standard" | "hero";
  size?: number;
  style?: StyleProp<ViewStyle>;
  /** Draw callout nodes around the engine (reel technique). */
  callouts?: { id: string; label: string; side: "left" | "right"; top: number }[];
  calloutsActive?: boolean;
}

/**
 * Stage under the Decision Engine: perspective grid + scan beam
 * (motion-graphics floor without purple portfolio styling).
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
  const gridPulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (reduceMotion) {
      scan.setValue(0.4);
      gridPulse.setValue(0.5);
      return;
    }
    const beam = Animated.loop(
      Animated.timing(scan, {
        toValue: 1,
        duration: tone === "loading" ? 1800 : 4200,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(gridPulse, {
          toValue: 1,
          duration: 2200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(gridPulse, {
          toValue: 0,
          duration: 2200,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    beam.start();
    pulse.start();
    return () => {
      beam.stop();
      pulse.stop();
    };
  }, [gridPulse, reduceMotion, scan, tone]);

  const scanX = scan.interpolate({
    inputRange: [0, 1],
    outputRange: [-40, 280],
  });
  const floorOpacity = gridPulse.interpolate({
    inputRange: [0, 1],
    outputRange: [0.35, 0.7],
  });

  const rows = intensity === "hero" ? 7 : 5;
  const cols = intensity === "hero" ? 9 : 7;

  return (
    <View style={[styles.stage, style]}>
      <View style={styles.floorWrap} pointerEvents="none">
        <Animated.View style={[styles.floor, { opacity: floorOpacity }]}>
          {Array.from({ length: rows }).map((_, row) => (
            <View key={`r-${row}`} style={styles.gridRow}>
              {Array.from({ length: cols }).map((__, col) => (
                <View
                  key={`c-${col}`}
                  style={[
                    styles.cell,
                    (row + col) % 2 === 0 && styles.cellAlt,
                    tone === "verified" && styles.cellVerified,
                    tone === "loading" && styles.cellLoading,
                  ]}
                />
              ))}
            </View>
          ))}
          <Animated.View style={[styles.scanBeam, { transform: [{ translateX: scanX }] }]}>
            <LinearGradient
              colors={["transparent", "rgba(26,168,240,0.45)", "rgba(240,193,74,0.35)", "transparent"]}
              start={{ x: 0, y: 0.5 }}
              end={{ x: 1, y: 0.5 }}
              style={StyleSheet.absoluteFill}
            />
          </Animated.View>
          <LinearGradient
            colors={["transparent", "rgba(2,5,10,0.55)", "rgba(2,5,10,0.95)"]}
            style={styles.floorFade}
          />
        </Animated.View>
      </View>
      <View style={styles.orbitWrap}>
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
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  stage: {
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    paddingBottom: 8,
  },
  orbitWrap: {
    width: "100%",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 220,
  },
  floorWrap: {
    position: "absolute",
    bottom: 8,
    left: 12,
    right: 12,
    height: 88,
    overflow: "hidden",
    borderRadius: 16,
  },
  floor: {
    flex: 1,
    transform: [{ perspective: 400 }, { rotateX: "58deg" }, { scale: 1.15 }],
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(26,168,240,0.25)",
    backgroundColor: "rgba(6,18,28,0.65)",
  },
  gridRow: {
    flex: 1,
    flexDirection: "row",
  },
  cell: {
    flex: 1,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(26,168,240,0.12)",
  },
  cellAlt: {
    backgroundColor: "rgba(26,168,240,0.05)",
  },
  cellVerified: {
    borderColor: "rgba(46,229,154,0.18)",
  },
  cellLoading: {
    borderColor: "rgba(240,193,74,0.2)",
  },
  scanBeam: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: 56,
  },
  floorFade: {
    ...StyleSheet.absoluteFill,
  },
});
