import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, spacing, type } from "@/theme";
import type { TicketCard } from "@/types";

import { PlayerPortrait } from "./PlayerPortrait";
import { MetalPanel } from "./MetalPanel";
import { StatusPill } from "./StatusPill";

export function TicketCardView({
  card,
  onPress,
}: {
  card: TicketCard;
  onPress?: () => void;
}) {
  return (
    <Pressable onPress={onPress} disabled={!onPress}>
      {({ pressed }) => (
        <MetalPanel
          tone={card.legs.length ? "gold" : "danger"}
          style={pressed ? styles.pressed : undefined}
        >
          <View style={styles.header}>
            <View style={styles.headerCopy}>
              <Text style={type.eyebrow}>YWP OFFICIAL CARD</Text>
              <Text style={styles.title}>{card.label}</Text>
            </View>
            <Text style={styles.score}>{card.confidence_score}</Text>
          </View>
          <View style={styles.statusRow}>
            <StatusPill value={card.legs.length ? card.risk : "PASS"} />
            <Text style={styles.legCount}>{card.legs.length} LEGS</Text>
          </View>
          {card.legs.map((leg, index) => (
            <View key={leg.id} style={styles.leg}>
              <Text style={styles.number}>{index + 1}</Text>
              <PlayerPortrait
                imageUrl={leg.image_url}
                teamImageUrl={leg.team_image_url}
                sport={leg.sport}
                size={36}
              />
              <View style={styles.legCopy}>
                <Text style={styles.selection}>{leg.selection}</Text>
                <Text style={type.caption}>
                  YIS {leg.ywp_rating} • {leg.confidence_score}% • {leg.risk_tier}
                </Text>
              </View>
              <Text style={styles.odds}>
                {leg.american_odds > 0 ? "+" : ""}
                {leg.american_odds}
              </Text>
            </View>
          ))}
          {card.warnings.slice(0, 2).map((warning) => (
            <Text key={warning} style={styles.warning}>
              {warning}
            </Text>
          ))}
          {onPress && card.legs.length ? (
            <Text style={styles.action}>OPEN & SAVE TICKET →</Text>
          ) : null}
        </MetalPanel>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pressed: { opacity: 0.85, transform: [{ scale: 0.99 }] },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  headerCopy: { flex: 1, gap: 2 },
  title: { color: colors.white, fontSize: 20, fontWeight: "900" },
  score: { color: colors.gold, fontSize: 34, fontWeight: "900" },
  statusRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  legCount: { color: colors.muted, fontSize: 11, fontWeight: "800" },
  leg: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  number: {
    color: colors.background,
    backgroundColor: colors.gold,
    width: 28,
    height: 28,
    borderRadius: 14,
    textAlign: "center",
    textAlignVertical: "center",
    lineHeight: 28,
    fontWeight: "900",
  },
  legCopy: { flex: 1, gap: 2 },
  selection: { color: colors.white, fontWeight: "800", fontSize: 14 },
  odds: { color: colors.gold, fontWeight: "900" },
  warning: { color: colors.warning, fontSize: 11, lineHeight: 16 },
  action: {
    color: colors.gold,
    textAlign: "right",
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0.6,
  },
});
