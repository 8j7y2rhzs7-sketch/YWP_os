import { useEffect, useMemo, useRef, type ReactNode } from "react";
import {
  Animated,
  Easing,
  StyleSheet,
  Text,
  View,
  type ImageSourcePropType,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { brandAssets } from "@/brandAssets";
import { EngineHeroLoop } from "@/components/EngineHeroLoop";
import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors, fonts, spacing } from "@/theme";

export type OrbitTone = "idle" | "loading" | "verified" | "partial" | "danger";

interface EngineOrbitProps {
  size?: number;
  tone?: OrbitTone;
  label?: string;
  /** Amplifies ring count, shockwaves, and orbiting ticks (Home hero). */
  intensity?: "standard" | "hero";
  source?: ImageSourcePropType;
  children?: ReactNode;
  style?: StyleProp<ViewStyle>;
}

const toneRing: Record<OrbitTone, string> = {
  idle: colors.circuitBlue,
  loading: colors.gold,
  verified: colors.success,
  partial: colors.warning,
  danger: colors.danger,
};

const TICK_COUNT = 24;

/**
 * Focal Decision Engine motion graphic:
 * counter-rotating rings, expanding shockwaves, radar sweep, orbiting ticks.
 */
export function EngineOrbit({
  size = 220,
  tone = "idle",
  label,
  intensity = "standard",
  source = brandAssets.decisionEngineEmblem,
  children,
  style,
}: EngineOrbitProps) {
  const reduceMotion = useReduceMotion();
  const breathe = useRef(new Animated.Value(0)).current;
  const spinA = useRef(new Animated.Value(0)).current;
  const spinB = useRef(new Animated.Value(0)).current;
  const sweep = useRef(new Animated.Value(0)).current;
  const wave = useRef(new Animated.Value(0)).current;
  const settle = useRef(new Animated.Value(0)).current;
  const emblemFloat = useRef(new Animated.Value(0)).current;

  const hero = intensity === "hero";
  const ringColor = toneRing[tone];
  const fast = tone === "loading";

  useEffect(() => {
    settle.setValue(0);
    Animated.spring(settle, {
      toValue: 1,
      friction: 7,
      tension: 58,
      useNativeDriver: true,
    }).start();
  }, [settle, tone]);

  useEffect(() => {
    if (reduceMotion) {
      breathe.setValue(0.5);
      spinA.setValue(0);
      spinB.setValue(0);
      sweep.setValue(0.2);
      wave.setValue(0.35);
      emblemFloat.setValue(0.5);
      return;
    }

    const loops: Animated.CompositeAnimation[] = [];

    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(breathe, {
          toValue: 1,
          duration: fast ? 900 : 2800,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(breathe, {
          toValue: 0,
          duration: fast ? 900 : 2800,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    loops.push(pulse);

    const rotateA = Animated.loop(
      Animated.timing(spinA, {
        toValue: 1,
        duration: fast ? 4200 : hero ? 14000 : 18000,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    loops.push(rotateA);

    const rotateB = Animated.loop(
      Animated.timing(spinB, {
        toValue: 1,
        duration: fast ? 6200 : hero ? 22000 : 26000,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    loops.push(rotateB);

    const radar = Animated.loop(
      Animated.timing(sweep, {
        toValue: 1,
        duration: fast ? 2400 : hero ? 4800 : 6400,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    loops.push(radar);

    const shock = Animated.loop(
      Animated.sequence([
        Animated.timing(wave, {
          toValue: 1,
          duration: fast ? 1400 : hero ? 2600 : 3600,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(wave, {
          toValue: 0,
          duration: 0,
          useNativeDriver: true,
        }),
        Animated.delay(fast ? 200 : 700),
      ]),
    );
    loops.push(shock);

    const float = Animated.loop(
      Animated.sequence([
        Animated.timing(emblemFloat, {
          toValue: 1,
          duration: 2400,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
        Animated.timing(emblemFloat, {
          toValue: 0,
          duration: 2400,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true,
        }),
      ]),
    );
    loops.push(float);

    for (const loop of loops) loop.start();
    return () => {
      for (const loop of loops) loop.stop();
      spinA.setValue(0);
      spinB.setValue(0);
      sweep.setValue(0);
      wave.setValue(0);
    };
  }, [
    breathe,
    emblemFloat,
    fast,
    hero,
    reduceMotion,
    spinA,
    spinB,
    sweep,
    tone,
    wave,
  ]);

  const outer = size;
  const mid = size * 0.82;
  const inner = size * 0.64;
  const core = size * 0.48;
  const emblem = size * (hero ? 0.44 : 0.4);

  const ringScale = breathe.interpolate({
    inputRange: [0, 1],
    outputRange: [1, fast ? 1.055 : 1.032],
  });
  const ringOpacity = breathe.interpolate({
    inputRange: [0, 1],
    outputRange: [0.35, 0.95],
  });
  const rotateCW = spinA.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });
  const rotateCCW = spinB.interpolate({
    inputRange: [0, 1],
    outputRange: ["360deg", "0deg"],
  });
  const sweepRotate = sweep.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });
  const floatY = emblemFloat.interpolate({
    inputRange: [0, 1],
    outputRange: [0, hero ? -14 : -8],
  });
  const floatScale = emblemFloat.interpolate({
    inputRange: [0, 1],
    outputRange: [1, hero ? 1.04 : 1.02],
  });
  const glowOpacity = breathe.interpolate({
    inputRange: [0, 1],
    outputRange: [0.4, 0.95],
  });
  const waveScale = wave.interpolate({
    inputRange: [0, 1],
    outputRange: [0.5, hero ? 1.55 : 1.32],
  });
  const waveOpacity = wave.interpolate({
    inputRange: [0, 0.12, 1],
    outputRange: [0.7, 0.4, 0],
  });

  const ticks = useMemo(() => {
    return Array.from({ length: TICK_COUNT }, (_, i) => {
      const angle = (360 / TICK_COUNT) * i;
      const major = i % 6 === 0;
      return { angle, major, index: i };
    });
  }, []);

  return (
    <Animated.View
      style={[
        styles.wrap,
        { width: outer + 24, height: outer + 24 },
        style,
        {
          opacity: settle,
          transform: [
            {
              scale: settle.interpolate({
                inputRange: [0, 1],
                outputRange: [0.88, 1],
              }),
            },
          ],
        },
      ]}
    >
      {/* Expanding shockwave — Rolls-Royce grid-ring energy, gold/blue */}
      <Animated.View
        pointerEvents="none"
        style={[
          styles.shock,
          {
            width: outer,
            height: outer,
            borderRadius: outer / 2,
            borderColor: ringColor,
            opacity: waveOpacity,
            transform: [{ scale: waveScale }],
          },
        ]}
      />
      {hero ? (
        <Animated.View
          pointerEvents="none"
          style={[
            styles.shock,
            styles.shockGold,
            {
              width: outer * 0.92,
              height: outer * 0.92,
              borderRadius: (outer * 0.92) / 2,
              opacity: wave.interpolate({
                inputRange: [0, 0.2, 1],
                outputRange: [0, 0.4, 0],
              }),
              transform: [
                {
                  scale: wave.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0.7, 1.28],
                  }),
                },
              ],
            },
          ]}
        />
      ) : null}

      {/* Outer counter-clockwise ring with tick marks */}
      <Animated.View
        pointerEvents="none"
        style={[
          styles.ringLayer,
          {
            width: outer,
            height: outer,
            opacity: ringOpacity,
            transform: [{ rotate: rotateCCW }, { scale: ringScale }],
          },
        ]}
      >
        <View
          style={[
            styles.ringBorder,
            {
              width: outer,
              height: outer,
              borderRadius: outer / 2,
              borderColor: ringColor,
            },
          ]}
        />
        {ticks.map((tick) => (
          <View
            key={tick.index}
            style={[
              styles.tickWrap,
              {
                width: outer,
                height: outer,
                transform: [{ rotate: `${tick.angle}deg` }],
                opacity: tick.major ? 0.95 : 0.4,
              },
            ]}
          >
            <View
              style={[
                styles.tick,
                tick.major && styles.tickMajor,
                { backgroundColor: tick.major ? colors.goldBright : ringColor },
              ]}
            />
          </View>
        ))}
      </Animated.View>

      {/* Mid dashed ring — clockwise */}
      <Animated.View
        pointerEvents="none"
        style={[
          styles.ring,
          styles.ringDashed,
          {
            width: mid,
            height: mid,
            borderRadius: mid / 2,
            borderColor: colors.gold,
            opacity: ringOpacity,
            transform: [{ rotate: rotateCW }, { scale: ringScale }],
          },
        ]}
      />

      {/* Inner solid ring */}
      <Animated.View
        pointerEvents="none"
        style={[
          styles.ring,
          {
            width: inner,
            height: inner,
            borderRadius: inner / 2,
            borderColor: "rgba(255,255,255,0.22)",
            opacity: 0.95,
            transform: [{ rotate: rotateCCW }],
          },
        ]}
      />

      {/* Radar sweep wedge */}
      <Animated.View
        pointerEvents="none"
        style={[
          styles.sweepLayer,
          {
            width: outer,
            height: outer,
            transform: [{ rotate: sweepRotate }],
          },
        ]}
      >
        <LinearGradient
          colors={[
            "transparent",
            `${ringColor}00`,
            `${ringColor}55`,
            `${ringColor}00`,
          ]}
          start={{ x: 0.5, y: 0.5 }}
          end={{ x: 1, y: 0.15 }}
          style={styles.sweep}
        />
      </Animated.View>

      {/* Orbiting signal dots — denser swarm */}
      {[0, 45, 90, 135, 180, 225, 270, 315].map((offset) => (
        <Animated.View
          key={offset}
          pointerEvents="none"
          style={[
            styles.dotOrbit,
            {
              width: core * (offset % 90 === 0 ? 1 : 0.86),
              height: core * (offset % 90 === 0 ? 1 : 0.86),
              transform: [
                {
                  rotate: spinA.interpolate({
                    inputRange: [0, 1],
                    outputRange: [`${offset}deg`, `${offset + 360}deg`],
                  }),
                },
              ],
            },
          ]}
        >
          <View
            style={[
              styles.dot,
              {
                width: offset % 90 === 0 ? 8 : 5,
                height: offset % 90 === 0 ? 8 : 5,
                borderRadius: 4,
                backgroundColor: offset % 90 === 0 ? colors.goldBright : ringColor,
                shadowColor: offset % 90 === 0 ? colors.gold : ringColor,
              },
            ]}
          />
        </Animated.View>
      ))}

      <Animated.View
        style={[
          styles.coreGlow,
          {
            width: emblem + (fast ? 52 : 36),
            height: emblem + (fast ? 52 : 36),
            borderRadius: (emblem + (fast ? 52 : 36)) / 2,
            opacity: glowOpacity,
            backgroundColor:
              tone === "loading"
                ? "rgba(240,193,74,0.28)"
                : tone === "verified"
                  ? "rgba(46,229,154,0.2)"
                  : "rgba(26,168,240,0.18)",
            borderColor:
              tone === "loading"
                ? "rgba(240,193,74,0.55)"
                : "rgba(240,193,74,0.35)",
            transform: [{ translateY: floatY }, { scale: Animated.multiply(ringScale, floatScale) }],
          },
        ]}
      />
      <Animated.View
        style={{
          transform: [{ translateY: floatY }, { scale: floatScale }],
        }}
      >
        <EngineHeroLoop
          size={emblem}
          shape="circle"
          sourceStill={source}
        />
      </Animated.View>
      {label ? (
        <Animated.View style={[styles.labelWrap, { opacity: settle }]}>
          <Text style={styles.label}>{label}</Text>
        </Animated.View>
      ) : null}
      {children}
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignSelf: "center",
    alignItems: "center",
    justifyContent: "center",
  },
  shock: {
    position: "absolute",
    borderWidth: 2,
  },
  shockGold: {
    borderColor: colors.gold,
  },
  ringLayer: {
    position: "absolute",
    alignItems: "center",
    justifyContent: "center",
  },
  ringBorder: {
    position: "absolute",
    borderWidth: 1.5,
  },
  ring: {
    position: "absolute",
    borderWidth: StyleSheet.hairlineWidth * 2,
  },
  ringDashed: {
    borderStyle: "dashed",
    borderWidth: 1.5,
  },
  tickWrap: {
    position: "absolute",
    alignItems: "center",
  },
  tick: {
    width: 2,
    height: 7,
    marginTop: 2,
    borderRadius: 1,
  },
  tickMajor: {
    height: 12,
    width: 2.5,
  },
  sweepLayer: {
    position: "absolute",
    alignItems: "center",
    justifyContent: "center",
  },
  sweep: {
    width: "50%",
    height: "50%",
    position: "absolute",
    top: 0,
    right: 0,
    borderTopRightRadius: 999,
  },
  dotOrbit: {
    position: "absolute",
    alignItems: "center",
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginTop: -2,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.9,
    shadowRadius: 6,
    elevation: 4,
  },
  coreGlow: {
    position: "absolute",
    borderWidth: 1,
  },
  labelWrap: {
    position: "absolute",
    bottom: 2,
  },
  label: {
    color: colors.goldBright,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.4,
    textTransform: "uppercase",
    backgroundColor: "rgba(2,5,10,0.88)",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(240,193,74,0.35)",
  },
});
