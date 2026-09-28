import { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, Text, View } from "react-native";

import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors, fonts, spacing } from "@/theme";

interface Callout {
  id: string;
  label: string;
  side: "left" | "right";
  top: number;
}

interface EngineCalloutsProps {
  active: boolean;
  accent?: string;
  items: Callout[];
}

/**
 * Product-callout motion from the design reel:
 * lines draw from the engine core to labeled nodes, then text fades in.
 */
export function EngineCallouts({
  active,
  accent = colors.circuitBlueBright,
  items,
}: EngineCalloutsProps) {
  const reduceMotion = useReduceMotion();
  const draws = useRef(items.map(() => new Animated.Value(0))).current;
  const fades = useRef(items.map(() => new Animated.Value(0))).current;

  useEffect(() => {
    while (draws.length < items.length) draws.push(new Animated.Value(0));
    while (fades.length < items.length) fades.push(new Animated.Value(0));

    if (!active) {
      for (const v of draws) v.setValue(0);
      for (const v of fades) v.setValue(0);
      return;
    }
    if (reduceMotion) {
      for (const v of draws) v.setValue(1);
      for (const v of fades) v.setValue(1);
      return;
    }

    const sequence = items.map((_, index) => {
      const draw = draws[index];
      const fade = fades[index];
      if (!draw || !fade) {
        return Animated.delay(0);
      }
      return Animated.sequence([
        Animated.delay(index * 180),
        Animated.timing(draw, {
          toValue: 1,
          duration: 560,
          easing: Easing.inOut(Easing.cubic),
          useNativeDriver: false,
        }),
        Animated.timing(fade, {
          toValue: 1,
          duration: 280,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]);
    });
    const batch = Animated.parallel(sequence);
    batch.start();
    return () => batch.stop();
  }, [active, draws, fades, items, reduceMotion]);

  return (
    <View pointerEvents="none" style={styles.wrap}>
      {items.map((item, index) => {
        const draw = draws[index] ?? new Animated.Value(0);
        const fade = fades[index] ?? new Animated.Value(0);
        const isLeft = item.side === "left";
        const width = draw.interpolate({
          inputRange: [0, 1],
          outputRange: [0, 72],
        });
        return (
          <View
            key={item.id}
            style={[
              styles.row,
              { top: item.top },
              isLeft ? styles.rowLeft : styles.rowRight,
            ]}
          >
            {isLeft ? (
              <>
                <Animated.View style={{ opacity: fade }}>
                  <Text style={[styles.label, { color: accent }]}>{item.label}</Text>
                </Animated.View>
                <Animated.View style={[styles.line, { width, backgroundColor: accent }]} />
                <Animated.View
                  style={[
                    styles.node,
                    {
                      borderColor: accent,
                      backgroundColor: accent,
                      opacity: fade,
                      transform: [
                        {
                          scale: fade.interpolate({
                            inputRange: [0, 1],
                            outputRange: [0.4, 1],
                          }),
                        },
                      ],
                    },
                  ]}
                />
              </>
            ) : (
              <>
                <Animated.View
                  style={[
                    styles.node,
                    {
                      borderColor: accent,
                      backgroundColor: accent,
                      opacity: fade,
                      transform: [
                        {
                          scale: fade.interpolate({
                            inputRange: [0, 1],
                            outputRange: [0.4, 1],
                          }),
                        },
                      ],
                    },
                  ]}
                />
                <Animated.View style={[styles.line, { width, backgroundColor: accent }]} />
                <Animated.View style={{ opacity: fade }}>
                  <Text style={[styles.label, { color: accent }]}>{item.label}</Text>
                </Animated.View>
              </>
            )}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    ...StyleSheet.absoluteFill,
  },
  row: {
    position: "absolute",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  rowLeft: {
    left: 4,
    right: "50%",
    justifyContent: "flex-end",
  },
  rowRight: {
    left: "50%",
    right: 4,
    justifyContent: "flex-start",
  },
  line: {
    height: 2,
    borderRadius: 1,
    opacity: 0.9,
  },
  node: {
    width: 8,
    height: 8,
    borderRadius: 4,
    borderWidth: 1.5,
  },
  label: {
    fontFamily: fonts.bodyBold,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1.1,
    textTransform: "uppercase",
    maxWidth: 100,
  },
});
