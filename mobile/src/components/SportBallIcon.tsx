import { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, Text } from "react-native";

import { useReduceMotion } from "@/hooks/useReduceMotion";

/**
 * Sport emoji/ball for the Select Sport grid.
 * Spins while the slate (or analysis) is loading for the active tile,
 * then settles with a short bounce when that load finishes.
 */
export function SportBallIcon({
  icon,
  spinning = false,
  size = 28,
}: {
  icon: string;
  spinning?: boolean;
  size?: number;
}) {
  const reduceMotion = useReduceMotion();
  const spin = useRef(new Animated.Value(0)).current;
  const bounceY = useRef(new Animated.Value(0)).current;
  const bounceScale = useRef(new Animated.Value(1)).current;
  const wasSpinning = useRef(false);

  useEffect(() => {
    if (reduceMotion) {
      spin.stopAnimation();
      bounceY.stopAnimation();
      bounceScale.stopAnimation();
      spin.setValue(0);
      bounceY.setValue(0);
      bounceScale.setValue(1);
      wasSpinning.current = false;
      return;
    }

    if (spinning) {
      wasSpinning.current = true;
      bounceY.setValue(0);
      bounceScale.setValue(1);
      spin.setValue(0);
      const loop = Animated.loop(
        Animated.timing(spin, {
          toValue: 1,
          duration: 820,
          easing: Easing.linear,
          useNativeDriver: true,
        }),
      );
      loop.start();
      return () => {
        loop.stop();
      };
    }

    if (!wasSpinning.current) {
      spin.setValue(0);
      return;
    }

    wasSpinning.current = false;
    spin.setValue(0);
    bounceY.setValue(0);
    bounceScale.setValue(1);
    Animated.parallel([
      Animated.sequence([
        Animated.timing(bounceY, {
          toValue: -9,
          duration: 110,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.spring(bounceY, {
          toValue: 0,
          friction: 3.2,
          tension: 260,
          useNativeDriver: true,
        }),
      ]),
      Animated.sequence([
        Animated.timing(bounceScale, {
          toValue: 1.16,
          duration: 110,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.spring(bounceScale, {
          toValue: 1,
          friction: 3.6,
          tension: 220,
          useNativeDriver: true,
        }),
      ]),
    ]).start();
  }, [spinning, reduceMotion, spin, bounceY, bounceScale]);

  const rotate = spin.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  return (
    <Animated.View
      style={[
        styles.wrap,
        {
          width: size + 4,
          height: size + 4,
          transform: [{ translateY: bounceY }, { scale: bounceScale }, { rotate }],
        },
      ]}
    >
      <Text style={[styles.icon, { fontSize: size, lineHeight: size + 4 }]}>{icon}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: "center",
    justifyContent: "center",
  },
  icon: {
    textAlign: "center",
  },
});
