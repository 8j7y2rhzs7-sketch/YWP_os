import { Image, StyleSheet, Text, View } from "react-native";

import { brandAssets } from "@/brandAssets";
import { sportLook } from "@/sportVisuals";
import { brand, colors, spacing, type } from "@/theme";

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
  return (
    <View style={[styles.wrap, compact && styles.wrapCompact]}>
      <Image
        source={brandAssets.crest}
        style={[styles.logo, compact && styles.logoCompact]}
        resizeMode="contain"
        accessibilityLabel="YWP OS crown emblem"
      />
      <View style={styles.copy}>
        <Text style={type.eyebrow}>{subtitle}</Text>
        <Text style={[styles.title, compact && styles.titleCompact]}>{title}</Text>
        {sport ? (
          <Text style={[styles.sportChip, { color: look.accent }]}>
            {look.emoji}  {look.label}
            {!compact ? `  •  PROTOCOL ${brand.protocolVersion}` : ""}
          </Text>
        ) : !compact ? (
          <Text style={styles.sportChip}>PROTOCOL {brand.protocolVersion}</Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
    borderBottomColor: colors.borderGold,
    borderBottomWidth: 1,
  },
  wrapCompact: { paddingTop: 0 },
  logo: { width: 76, height: 76, borderRadius: 38 },
  logoCompact: { width: 48, height: 48, borderRadius: 24 },
  copy: { flex: 1, gap: 2 },
  title: {
    color: colors.white,
    fontSize: 32,
    fontWeight: "900",
    letterSpacing: 0.6,
  },
  titleCompact: { fontSize: 23 },
  sportChip: {
    color: colors.gold,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
});
