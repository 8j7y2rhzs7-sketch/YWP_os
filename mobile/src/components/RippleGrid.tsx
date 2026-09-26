import { useEffect, useMemo, useRef } from "react";
import { Animated, Easing, StyleSheet, View } from "react-native";

import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors } from "@/theme";

interface RippleGridProps {
  rows?: number;
  cols?: number;
  active?: boolean;
  accent?: string;
  /** Faster radial wave when engine is loading/analyzing. */
  urgent?: boolean;
}

/**
 * Rolls-Royce reel floor: tiles lift in a radial ripple from center.
 */
export function RippleGrid({
  rows = 6,
  cols = 8,
  active = true,
  accent = colors.circuitBlue,
  urgent = false,
}: RippleGridProps) {
  const reduceMotion = useReduceMotion();
  const wave = useRef(new Animated.Value(0)).current;
  const cells = useMemo(() => {
    const midR = (rows - 1) / 2;
    const midC = (cols - 1) / 2;
    const out: { key: string; row: number; col: number; dist: number }[] = [];
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const dist = Math.hypot(row - midR, col - midC);
        out.push({ key: `${row}-${col}`, row, col, dist });
      }
    }
    return out;
  }, [cols, rows]);

  useEffect(() => {
    if (!active || reduceMotion) {
      wave.setValue(0.35);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(wave, {
          toValue: 1,
          duration: urgent ? 1400 : 2800,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(wave, {
          toValue: 0,
          duration: 0,
          useNativeDriver: true,
        }),
        Animated.delay(urgent ? 120 : 500),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [active, reduceMotion, urgent, wave]);

  const maxDist = Math.max(...cells.map((c) => c.dist), 1);

  return (
    <View style={styles.wrap}>
      {Array.from({ length: rows }).map((_, row) => (
        <View key={`row-${row}`} style={styles.row}>
          {Array.from({ length: cols }).map((__, col) => {
            const cell = cells.find((c) => c.row === row && c.col === col)!;
            const start = Math.max(0.02, cell.dist / maxDist);
            const peak = Math.min(0.98, start + 0.22);
            const lift = wave.interpolate({
              inputRange: [0, start, peak, 1],
              outputRange: [0, 0, -12, 0],
              extrapolate: "clamp",
            });
            const glow = wave.interpolate({
              inputRange: [0, start, peak, 1],
              outputRange: [0.1, 0.1, 0.85, 0.14],
              extrapolate: "clamp",
            });
            const grow = wave.interpolate({
              inputRange: [0, start, peak, 1],
              outputRange: [1, 1, 1.12, 1],
              extrapolate: "clamp",
            });
            return (
              <Animated.View
                key={cell.key}
                style={[
                  styles.cell,
                  {
                    borderColor: accent,
                    opacity: glow,
                    transform: [{ translateY: lift }, { scale: grow }],
                    backgroundColor:
                      (row + col) % 2 === 0
                        ? "rgba(26,168,240,0.07)"
                        : "rgba(240,193,74,0.05)",
                  },
                ]}
              />
            );
          })}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(26,168,240,0.28)",
    backgroundColor: "rgba(6,18,28,0.72)",
    overflow: "hidden",
  },
  row: { flex: 1, flexDirection: "row" },
  cell: {
    flex: 1,
    borderWidth: StyleSheet.hairlineWidth,
  },
});
