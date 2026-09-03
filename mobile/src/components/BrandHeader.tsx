import { Image, StyleSheet, Text, View } from "react-native";

import { brandAssets } from "@/brandAssets";
import { brand, colors, spacing, type } from "@/theme";

interface BrandHeaderProps {
  title?: string;
  subtitle?: string;
  compact?: boolean;
}

export function BrandHeader({
  title = brand.product,
  subtitle = brand.descriptor,
  compact = false,
}: BrandHeaderProps) {
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
        {!compact ? (
          <Text style={styles.protocol}>PROTOCOL {brand.protocolVersion}</Text>
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
  protocol: {
    color: colors.muted,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1.2,
  },
});
