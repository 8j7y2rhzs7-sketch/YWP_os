import { useEffect, useRef } from "react";
import { Animated, Image, StyleSheet, Text, View } from "react-native";

import { brandAssets } from "@/brandAssets";
import { sportLook } from "@/sportVisuals";
import { brand, colors, fonts, spacing, type } from "@/theme";

interface BrandHeaderProps {
  title?: string;
  subtitle?: string;
  compact?: boolean;
  sport?: string;
}

export function BrandHeader({
  title = brand.product,
  subtitle = brand.descriptor,
  compact = false,
  sport,
}: BrandHeaderProps) {
  const look = sportLook(sport);
  const enter = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    enter.setValue(0);
    Animated.spring(enter, {
      toValue: 1,
      friction: 8,
      tension: 58,
      useNativeDriver: true,
    }).start();
  }, [enter, sport]);

  return (
    <Animated.View
      style={[
        styles.wrap,
        compact && styles.wrapCompact,
        {
          opacity: enter,
          transform: [
            {
              translateY: enter.interpolate({
                inputRange: [0, 1],
                outputRange: [10, 0],
              }),
            },
          ],
        },
      ]}
    >
      {sport ? <View style={[styles.sportStripe, { backgroundColor: look.accent }]} /> : null}
      <View style={styles.crestGlow}>
        <Image
          source={brandAssets.crest}
          style={[styles.logo, compact && styles.logoCompact]}
          resizeMode="contain"
          accessibilityLabel="YWP OS crown emblem"
        />
      </View>
      <View style={styles.copy}>
        <Text style={type.eyebrow}>{subtitle}</Text>
        <Text style={[styles.title, compact && styles.titleCompact]}>{title}</Text>
        {sport ? (
          <Text style={[styles.sportChip, { color: look.accent }]}>
            {look.label}
            {!compact ? `  ·  ${brand.skin}` : ""}
          </Text>
        ) : !compact ? (
          <Text style={styles.sportChip}>
            {brand.skin} · PROTOCOL {brand.protocolVersion}
          </Text>
        ) : null}
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
    borderBottomColor: "rgba(196,152,42,0.4)",
    borderBottomWidth: StyleSheet.hairlineWidth,
    overflow: "hidden",
  },
  wrapCompact: { paddingTop: 0, paddingBottom: spacing.sm },
  sportStripe: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    width: 3,
    opacity: 0.95,
  },
  crestGlow: {
    borderRadius: 40,
    padding: 2,
    backgroundColor: "rgba(240,193,74,0.14)",
    borderWidth: 1,
    borderColor: "rgba(240,193,74,0.34)",
  },
  logo: { width: 76, height: 76, borderRadius: 38 },
  logoCompact: { width: 48, height: 48, borderRadius: 24 },
  copy: { flex: 1, gap: 3 },
  title: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 36,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  titleCompact: { fontSize: 24 },
  sportChip: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.7,
    textTransform: "uppercase",
  },
});
