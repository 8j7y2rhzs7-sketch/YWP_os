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
    Animated.spring(enter, {
      toValue: 1,
      friction: 8,
      tension: 60,
      useNativeDriver: true,
    }).start();
  }, [enter]);

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
                outputRange: [8, 0],
              }),
            },
          ],
        },
      ]}
    >
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
            {!compact ? `  ·  PROTOCOL ${brand.protocolVersion}` : ""}
          </Text>
        ) : !compact ? (
          <Text style={styles.sportChip}>PROTOCOL {brand.protocolVersion}</Text>
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
    borderBottomColor: "rgba(196,152,42,0.35)",
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  wrapCompact: { paddingTop: 0, paddingBottom: spacing.sm },
  crestGlow: {
    borderRadius: 40,
    padding: 2,
    backgroundColor: "rgba(240,193,74,0.12)",
    borderWidth: 1,
    borderColor: "rgba(240,193,74,0.28)",
  },
  logo: { width: 72, height: 72, borderRadius: 36 },
  logoCompact: { width: 46, height: 46, borderRadius: 23 },
  copy: { flex: 1, gap: 3 },
  title: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 34,
    fontWeight: "800",
    letterSpacing: -0.4,
  },
  titleCompact: { fontSize: 24 },
  sportChip: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
});
