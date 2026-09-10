import { useEffect, useMemo, useRef } from "react";
import {
  Animated,
  Easing,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { brandAssets } from "@/brandAssets";
import { MetalShimmer } from "@/components/MetalShimmer";
import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors, fonts, radius, spacing, type } from "@/theme";
import type { DayForgeResponse } from "@/types";

function heatLabel(progress: number, status: DayForgeResponse["status"]): string {
  if (status === "ready") return "SEALED · READY";
  if (status === "pass") return "FORGE PASS";
  if (status === "unavailable") return "STANDING BY";
  if (progress >= 0.78) return "CRITICAL HEAT";
  if (progress >= 0.45) return "COOKING";
  return "WARMING";
}

/**
 * Bottom-of-Home Day Forge chamber — cooks with heat pulse until the vault opens.
 */
export function DayForgeChamber({
  forge,
  onPress,
}: {
  forge: DayForgeResponse | null;
  onPress?: () => void;
}) {
  const reduceMotion = useReduceMotion();
  const heat = useRef(new Animated.Value(0)).current;
  const glow = useRef(new Animated.Value(0.35)).current;
  const shake = useRef(new Animated.Value(0)).current;
  const progress = forge?.progress ?? 0.12;
  const status = forge?.status ?? "cooking";
  const ready = status === "ready";
  const pass = status === "pass";

  useEffect(() => {
    if (reduceMotion) {
      heat.setValue(progress);
      glow.setValue(ready ? 1 : 0.45);
      return;
    }
    Animated.timing(heat, {
      toValue: progress,
      duration: 900,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();

    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(glow, {
          toValue: ready ? 1 : 0.35 + progress * 0.55,
          duration: ready ? 900 : 1400,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(glow, {
          toValue: ready ? 0.72 : 0.22 + progress * 0.25,
          duration: ready ? 900 : 1400,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    pulse.start();

    let tremor: Animated.CompositeAnimation | null = null;
    if (!ready && progress > 0.55) {
      tremor = Animated.loop(
        Animated.sequence([
          Animated.timing(shake, {
            toValue: 1,
            duration: 60,
            useNativeDriver: true,
          }),
          Animated.timing(shake, {
            toValue: -1,
            duration: 60,
            useNativeDriver: true,
          }),
          Animated.timing(shake, {
            toValue: 0,
            duration: 60,
            useNativeDriver: true,
          }),
          Animated.delay(900),
        ]),
      );
      tremor.start();
    }

    return () => {
      pulse.stop();
      tremor?.stop();
    };
  }, [glow, heat, progress, ready, reduceMotion, shake]);

  const art = useMemo(
    () => (ready ? brandAssets.dayForgeOpenDock : brandAssets.dayForgeSealedDock),
    [ready],
  );

  const barWidth = heat.interpolate({
    inputRange: [0, 1],
    outputRange: ["6%", "100%"],
  });

  const translateX = shake.interpolate({
    inputRange: [-1, 1],
    outputRange: [-2.5, 2.5],
  });

  return (
    <Pressable onPress={onPress} disabled={!onPress && !ready}>
      <LinearGradient
        colors={
          ready
            ? ["#3C2C0A", "#0A1824", "#05080C"]
            : pass
              ? ["#2A1218", "#0A1018", "#05080C"]
              : ["#0A1C28", "#081018", "#120E06"]
        }
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.chamber}
      >
        <Animated.View
          style={[
            styles.glowRing,
            {
              opacity: glow,
              transform: [{ translateX }],
            },
          ]}
        />
        <View style={styles.row}>
          <Animated.View style={{ transform: [{ translateX }], opacity: glow }}>
            <Image source={art} style={styles.emblem} resizeMode="contain" />
          </Animated.View>
          <View style={styles.copy}>
            <MetalShimmer intensity={ready ? "bright" : "soft"} periodMs={ready ? 1800 : 2600}>
              <Text style={styles.kicker}>DAY FORGE</Text>
            </MetalShimmer>
            <Text style={styles.title}>
              {ready
                ? "Vault open"
                : pass
                  ? "No forced play"
                  : "Cooking today's play"}
            </Text>
            <Text style={styles.message} numberOfLines={2}>
              {forge?.message ?? "Decision Engine is gathering heat for a cash-band play…"}
            </Text>
            <Text style={styles.heatMeta}>
              {heatLabel(progress, status)} · {Math.round(progress * 100)}%
              {forge?.sport ? ` · ${forge.sport.toUpperCase()}` : ""}
            </Text>
          </View>
        </View>

        <View style={styles.track}>
          <Animated.View style={[styles.fillWrap, { width: barWidth }]}>
            <LinearGradient
              colors={
                ready
                  ? [colors.goldBright, colors.gold, colors.circuitBlue]
                  : [colors.circuitBlueDeep, colors.circuitBlue, colors.gold]
              }
              start={{ x: 0, y: 0.5 }}
              end={{ x: 1, y: 0.5 }}
              style={styles.fill}
            />
          </Animated.View>
        </View>

        {ready ? (
          <Text style={styles.cta}>TAP TO REVEAL</Text>
        ) : (
          <Text style={styles.ctaMuted}>
            Not juice · not lottery · only when the data is ready
          </Text>
        )}
      </LinearGradient>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chamber: {
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(240,193,74,0.38)",
    padding: spacing.lg,
    gap: spacing.md,
    overflow: "hidden",
    minHeight: 168,
  },
  glowRing: {
    position: "absolute",
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: "rgba(26,168,240,0.16)",
    top: -40,
    left: -30,
  },
  row: {
    flexDirection: "row",
    gap: spacing.md,
    alignItems: "center",
  },
  emblem: {
    width: 92,
    height: 92,
  },
  copy: {
    flex: 1,
    gap: 4,
  },
  kicker: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 13,
    letterSpacing: 2.4,
  },
  title: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 22,
    letterSpacing: -0.4,
  },
  message: {
    ...type.caption,
    color: colors.silver,
    lineHeight: 16,
  },
  heatMeta: {
    marginTop: 4,
    color: colors.circuitBlueBright,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    letterSpacing: 0.6,
  },
  track: {
    height: 8,
    borderRadius: 999,
    backgroundColor: "rgba(255,255,255,0.06)",
    overflow: "hidden",
  },
  fillWrap: {
    height: "100%",
  },
  fill: {
    flex: 1,
    borderRadius: 999,
  },
  cta: {
    color: colors.goldBright,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    letterSpacing: 1.8,
    textAlign: "center",
  },
  ctaMuted: {
    color: colors.dim,
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
    textAlign: "center",
  },
});
