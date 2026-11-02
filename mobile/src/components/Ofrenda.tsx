import { useEffect, useRef } from "react";
import { Animated, Image, StyleSheet, Text, View } from "react-native";

import { brandAssets } from "@/brandAssets";
import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors, fonts, holiday, spacing } from "@/theme";

const BEATS = ["Analyze", "Weigh", "Decide", "Adapt", "Execute"] as const;

function Candle({
  label,
  tall,
  flicker,
}: {
  label: string;
  tall?: boolean;
  flicker: Animated.Value;
}) {
  const scale = flicker.interpolate({
    inputRange: [0, 1],
    outputRange: tall ? [1, 1.18] : [0.92, 1.05],
  });
  return (
    <View style={styles.beat}>
      <Animated.View style={[styles.flame, tall && styles.flameTall, { transform: [{ scale }] }]} />
      <View style={[styles.wax, tall && styles.waxTall]} />
      <Text style={[styles.beatLabel, tall && styles.beatLabelLive]}>{label}</Text>
    </View>
  );
}

/** The holiday is the night the plays stay up. The logo is not part of this. */
export function Ofrenda() {
  const reduceMotion = useReduceMotion();
  const flicker = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (reduceMotion) {
      flicker.setValue(0.6);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(flicker, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(flicker, { toValue: 0, duration: 900, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [flicker, reduceMotion]);

  return (
    <View style={styles.altar} accessibilityLabel="Día de Muertos. Five candles for the protocol. The plays stay up.">
      <View style={styles.row}>
        {BEATS.map((beat, index) => (
          <View key={beat} style={styles.slot}>
            {index > 0 ? <View style={styles.petal} /> : null}
            <Candle label={beat} tall={beat === "Decide"} flicker={flicker} />
          </View>
        ))}
      </View>
      <View style={styles.caption}>
        <Image
          source={brandAssets.crest}
          style={styles.crest}
          resizeMode="contain"
          accessibilityIgnoresInvertColors
          accessibilityLabel="YWP Decision Engine"
        />
        <View style={styles.captionCopy}>
          <Text style={styles.name}>{holiday.name}</Text>
          <Text style={styles.line}>The plays stay up after you leave.</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  altar: {
    gap: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xs,
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
  },
  slot: {
    flex: 1,
    alignItems: "center",
    justifyContent: "flex-end",
  },
  petal: {
    position: "absolute",
    left: -6,
    bottom: 28,
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: holiday.petal,
    opacity: 0.9,
  },
  beat: { alignItems: "center", gap: 4 },
  flame: {
    width: 10,
    height: 16,
    borderRadius: 8,
    backgroundColor: holiday.candle,
    shadowColor: holiday.candle,
    shadowOpacity: 0.9,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 0 },
  },
  flameTall: {
    width: 14,
    height: 24,
    borderRadius: 10,
    backgroundColor: "#FFE08A",
  },
  wax: {
    width: 12,
    height: 18,
    borderTopLeftRadius: 2,
    borderTopRightRadius: 2,
    borderBottomLeftRadius: 3,
    borderBottomRightRadius: 3,
    backgroundColor: holiday.wax,
  },
  waxTall: { height: 26, width: 14 },
  beatLabel: {
    color: colors.muted,
    fontFamily: fonts.bodyBold,
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
  beatLabelLive: { color: holiday.candle },
  caption: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  crest: { width: 36, height: 36 },
  captionCopy: { flex: 1, gap: 2 },
  name: {
    color: holiday.candle,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.6,
  },
  line: {
    color: colors.silver,
    fontFamily: fonts.body,
    fontSize: 13,
  },
});
