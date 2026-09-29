import { useEffect, useRef, useState } from "react";
import { Animated, Easing, StyleSheet, Text, type TextStyle } from "react-native";

import { useReduceMotion } from "@/hooks/useReduceMotion";
import { fonts } from "@/theme";

interface CountUpProps {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  durationMs?: number;
  style?: TextStyle;
  formatter?: (n: number) => string;
}

/** Reel-style number tick — values climb into place instead of hard-cutting. */
export function CountUp({
  value,
  prefix = "",
  suffix = "",
  decimals = 0,
  durationMs = 900,
  style,
  formatter,
}: CountUpProps) {
  const reduceMotion = useReduceMotion();
  const anim = useRef(new Animated.Value(0)).current;
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (reduceMotion) {
      setDisplay(value);
      return;
    }
    anim.setValue(0);
    const id = anim.addListener(({ value: t }) => {
      setDisplay(t * value);
    });
    Animated.timing(anim, {
      toValue: 1,
      duration: durationMs,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();
    return () => {
      anim.removeListener(id);
    };
  }, [anim, durationMs, reduceMotion, value]);

  const label = formatter
    ? formatter(display)
    : `${prefix}${display.toFixed(decimals)}${suffix}`;

  return <Text style={[styles.text, style]}>{label}</Text>;
}

const styles = StyleSheet.create({
  text: {
    fontFamily: fonts.displaySemi,
    fontWeight: "700",
  },
});
