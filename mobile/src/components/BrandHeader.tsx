import { useEffect, useRef } from "react";
import { Animated, Image, StyleSheet, Text, View } from "react-native";

import { brandAssets } from "@/brandAssets";
import { MetalShimmer } from "@/components/MetalShimmer";
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
      friction: 7,
      tension: 64,
      useNativeDriver: true,
    }).start();
  }, [enter, sport, title]);

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
                outputRange: [12, 0],
              }),
            },
          ],
        },
      ]}
    >
      {sport ? <View style={[styles.sportStripe, { backgroundColor: look.accent }]} /> : null}
      <MetalShimmer intensity="soft" periodMs={3600} style={styles.crestGlow}>
        <Image
          source={brandAssets.crest}
          style={[styles.logo, compact && styles.logoCompact]}
          resizeMode="contain"
          accessibilityLabel="YWP OS crown emblem"
        />
      </MetalShimmer>
      <View style={styles.copy}>
        <Text style={[type.eyebrow, styles.eyebrow]}>{subtitle}</Text>
        <Text style={[styles.title, compact && styles.titleCompact]} numberOfLines={2}>
          {title}
        </Text>
        {sport ? (
          <Text style={[styles.sportChip, { color: look.accent }]}>
            {look.label}
            {!compact ? `  ·  ${brand.skin}` : ""}
          </Text>
        ) : !compact ? (
          <Text style={styles.sportChip}>
            {brand.tagline} · {brand.skin}
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
    gap: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
    borderBottomColor: "rgba(255,255,255,0.08)",
    borderBottomWidth: StyleSheet.hairlineWidth,
    overflow: "hidden",
  },
  wrapCompact: { paddingTop: 0, paddingBottom: spacing.md },
  sportStripe: {
    position: "absolute",
    left: 0,
    top: 4,
    bottom: 4,
    width: 3,
    borderRadius: 2,
    opacity: 0.95,
  },
  crestGlow: {
    borderRadius: 18,
    padding: 3,
    backgroundColor: "rgba(26,168,240,0.12)",
    borderWidth: 1,
    borderColor: "rgba(26,168,240,0.38)",
  },
  logo: { width: 64, height: 64, borderRadius: 14 },
  logoCompact: { width: 44, height: 44, borderRadius: 11 },
  copy: { flex: 1, gap: 4 },
  eyebrow: { letterSpacing: 1.2 },
  title: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 30,
    fontWeight: "800",
    letterSpacing: -0.9,
    lineHeight: 34,
  },
  titleCompact: { fontSize: 22, lineHeight: 26, letterSpacing: -0.6 },
  sportChip: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.1,
    textTransform: "uppercase",
    marginTop: 2,
  },
});
