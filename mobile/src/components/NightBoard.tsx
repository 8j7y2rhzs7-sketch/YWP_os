import type { ReactNode } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { brandAssets } from "@/brandAssets";
import { colors, fonts, spacing, type } from "@/theme";

interface NightBoardProps {
  kicker: string;
  title: string;
  detail?: string | null;
  action?: ReactNode;
  tall?: boolean;
}

/** The screen itself: the glass, the line, the lock, the candle. */
export function NightBoard({ kicker, title, detail, action, tall = false }: NightBoardProps) {
  return (
    <View style={[styles.frame, tall ? styles.tall : styles.short]}>
      <Image
        source={brandAssets.nightBoard}
        style={StyleSheet.absoluteFill}
        resizeMode="cover"
        accessibilityLabel="Night board. A play has crossed the line. The lock is shut. One candle is lit."
        accessibilityIgnoresInvertColors
      />
      <LinearGradient
        colors={["rgba(2,5,10,0.15)", "rgba(2,5,10,0.25)", "rgba(2,5,10,0.92)"]}
        locations={[0, 0.42, 1]}
        style={StyleSheet.absoluteFill}
      />
      <View style={styles.copy}>
        <Text style={styles.kicker}>{kicker}</Text>
        <Text style={styles.title}>{title}</Text>
        {detail ? (
          <Text style={styles.detail} numberOfLines={3}>
            {detail}
          </Text>
        ) : null}
        {action}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: colors.background,
    justifyContent: "flex-end",
  },
  tall: { height: 520 },
  short: { height: 280 },
  copy: {
    gap: spacing.sm,
    padding: spacing.lg,
  },
  kicker: {
    ...type.eyebrow,
    color: "#F0C14A",
  },
  title: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: -0.8,
    lineHeight: 36,
  },
  detail: {
    ...type.body,
    color: colors.silver,
  },
});
