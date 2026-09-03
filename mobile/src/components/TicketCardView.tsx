import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, spacing, type } from "@/theme";
import type { TicketCard } from "@/types";

import { PlayerPortrait } from "./PlayerPortrait";
import { MetalPanel } from "./MetalPanel";
import { StatusPill } from "./StatusPill";

function formatStart(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

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
            <View style={styles.scoreWrap}>
              <Text style={styles.score}>{card.quality_score ?? card.confidence_score}</Text>
              <Text style={styles.scoreCaption}>QUALITY /100</Text>
            </View>
          </View>
          <View style={styles.statusRow}>
            <StatusPill value={card.legs.length ? card.risk : "PASS"} />
            <Text style={styles.legCount}>{card.legs.length} LEGS</Text>
          </View>
          {card.risk_explanation ? (
            <Text style={styles.meta}>{card.risk_explanation}</Text>
          ) : null}
          <Text style={styles.meta}>
            {card.quality_score_note ??
              "Card score is average YWP quality (0-100), not a win probability."}
          </Text>
          <Text style={styles.meta}>
            {card.joint_probability_note ??
              "Joint win probability unavailable unless every leg has an independent model probability."}
            {card.joint_win_probability != null
              ? ` Estimate: ${(card.joint_win_probability * 100).toFixed(1)}%.`
              : ""}
          </Text>
          {card.legs.map((leg) => {
            const teams =
              leg.away_team && leg.home_team
                ? `${leg.away_team} @ ${leg.home_team}`
                : leg.event_name;
            const start = formatStart(leg.start_time);
            const winP =
              leg.probability_available && leg.model_win_probability != null
                ? `Model win ${(leg.model_win_probability * 100).toFixed(1)}%`
                : "Model win unavailable";
            return (
              <View key={leg.id} style={styles.leg}>
                <View
                  style={[
                    styles.number,
                    card.weakest_leg_id === leg.id && styles.numberWeak,
                  ]}
                >
                  <Text style={styles.numberText}>
                    {card.weakest_leg_id === leg.id ? "W" : "•"}
                  </Text>
                </View>
                <PlayerPortrait
                  imageUrl={leg.image_url}
                  teamImageUrl={leg.team_image_url}
                  sport={leg.sport}
                  size={36}
                />
                <View style={styles.legCopy}>
                  <Text style={styles.selection}>{leg.selection}</Text>
                  <Text style={type.caption}>{teams}</Text>
                  <Text style={type.caption}>
                    {leg.market_scope_label ??
                      `${leg.market_period} · ${leg.market_type}`}
                    {start ? ` · ${start}` : ""}
                  </Text>
                  <Text style={type.caption}>
                    YIS {leg.ywp_rating} · Quality {leg.quality_score ?? leg.confidence_score}/100 ·{" "}
                    {winP}
                  </Text>
                  <Text style={type.caption}>
                    {leg.bookmaker_label ?? leg.bookmaker ?? "Book unknown"}
                    {leg.verification_status ? ` · ${leg.verification_status}` : ""}
                    {leg.risk_tier ? ` · ${leg.risk_tier}` : ""}
                  </Text>
                </View>
                <Text style={styles.odds}>
                  {leg.american_odds > 0 ? "+" : ""}
                  {leg.american_odds}
                </Text>
              </View>
            );
          })}
          {card.weakest_leg_explanation ? (
            <Text style={styles.warning}>{card.weakest_leg_explanation}</Text>
          ) : null}
          {card.warnings
            .filter((warning) => warning !== card.weakest_leg_explanation)
            .slice(0, 2)
            .map((warning) => (
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
  scoreWrap: { alignItems: "flex-end" },
  score: { color: colors.gold, fontSize: 34, fontWeight: "900" },
  scoreCaption: { color: colors.muted, fontSize: 9, fontWeight: "800", letterSpacing: 0.6 },
  statusRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  legCount: { color: colors.muted, fontSize: 11, fontWeight: "800" },
  meta: { color: colors.muted, fontSize: 11, lineHeight: 15 },
  leg: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  number: {
    backgroundColor: colors.gold,
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
  },
  numberWeak: { backgroundColor: colors.warning },
  numberText: { color: colors.background, fontWeight: "900", fontSize: 12 },
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
