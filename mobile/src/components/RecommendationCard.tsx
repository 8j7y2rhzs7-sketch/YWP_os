import { useEffect, useRef } from "react";
import { Animated, Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { sportLook } from "@/sportVisuals";
import { colors, fonts, radius, spacing, type } from "@/theme";
import type { Recommendation } from "@/types";

import { PlayerPortrait } from "./PlayerPortrait";
import { MetalPanel } from "./MetalPanel";
import { StatusPill } from "./StatusPill";

function odds(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}

export function RecommendationCard({
  item,
  compact = false,
  selected = false,
  onPress,
}: {
  item: Recommendation;
  compact?: boolean;
  selected?: boolean;
  onPress?: () => void;
}) {
  const skip = item.decision === "SKIP";
  const sourceUrl = item.source_urls?.[0];
  const look = sportLook(item.sport);
  const enter = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    enter.setValue(0);
    Animated.spring(enter, {
      toValue: 1,
      friction: 8,
      tension: 70,
      useNativeDriver: true,
    }).start();
  }, [enter, item.id]);

  const body = (
    <Animated.View
      style={{
        opacity: enter,
        transform: [
          {
            translateY: enter.interpolate({
              inputRange: [0, 1],
              outputRange: [12, 0],
            }),
          },
        ],
      }}
    >
      <MetalPanel
        tone={skip ? "danger" : selected ? "gold" : "default"}
        accent={look.accent}
        style={styles.panel}
      >
        <View style={styles.top}>
          <View style={[styles.rank, { backgroundColor: look.accent }]}>
            <Text style={styles.rankText}>{item.rank}</Text>
          </View>
          <PlayerPortrait
            imageUrl={item.image_url}
            teamImageUrl={item.team_image_url}
            sport={item.sport}
          />
          <View style={styles.titleWrap}>
            <Text style={[styles.market, { color: look.accent }]}>
              {item.sport.toUpperCase()} • {item.market_type.replaceAll("_", " ")}
            </Text>
            <Text style={styles.selection}>{item.selection}</Text>
            <Text style={type.caption}>{item.event_name}</Text>
            <Text style={type.caption}>
              {item.market_scope_label ??
                `${item.market_period} · ${item.market_type.replaceAll("_", " ")}`}
              {item.bookmaker_label ? ` · ${item.bookmaker_label}` : ""}
              {item.verification_status ? ` · ${item.verification_status}` : ""}
            </Text>
            <Text style={type.caption}>
              {item.probability_available && item.model_win_probability != null
                ? `Model win ${(Number(item.model_win_probability) * 100).toFixed(1)}%`
                : item.probability_unavailable_reason ??
                  "Model win probability unavailable"}
            </Text>
          </View>
          <View style={styles.right}>
            <Text style={styles.odds}>{odds(item.american_odds)}</Text>
            <Text style={styles.rating}>YIS {item.ywp_rating}</Text>
          </View>
        </View>
        <View style={styles.statusRow}>
          <StatusPill value={item.decision} />
          <Text style={styles.confidence}>
            QUALITY {item.quality_score ?? item.confidence_score}/100
          </Text>
          <Text style={styles.vision}>VISION {item.vision_score}</Text>
          {selected ? <Text style={styles.picked}>ON TICKET</Text> : null}
        </View>
        {!compact ? (
          <>
            <Text style={styles.reasoning}>{item.reasoning_summary}</Text>
            <View style={styles.tags}>
              {item.reason_codes.slice(0, 4).map((code) => (
                <Text key={code} style={styles.tag}>
                  {code.replaceAll("_", " ")}
                </Text>
              ))}
            </View>
            {item.warnings.length ? (
              <View style={styles.warningBox}>
                {item.warnings.slice(0, 3).map((warning) => (
                  <Text key={warning} style={styles.warningText}>
                    {warning}
                  </Text>
                ))}
              </View>
            ) : null}
            {item.safer_alternative ? (
              <Text style={styles.safer}>SAFER: {item.safer_alternative}</Text>
            ) : null}
            {item.live_trigger ? (
              <Text style={styles.live}>LIVE TRIGGER: {item.live_trigger}</Text>
            ) : null}
            {item.hedge ? (
              <Text style={styles.hedge}>HEDGE / CASH-OUT: {item.hedge}</Text>
            ) : null}
            {sourceUrl ? (
              <Pressable
                accessibilityRole="link"
                onPress={() => void Linking.openURL(sourceUrl)}
                style={styles.sourceLink}
              >
                <Text style={styles.sourceText}>OPEN OFFICIAL SOURCE</Text>
              </Pressable>
            ) : null}
          </>
        ) : null}
      </MetalPanel>
    </Animated.View>
  );
  if (!onPress) return body;
  return (
    <Pressable onPress={onPress} accessibilityRole="button">
      {body}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  panel: { padding: spacing.lg },
  top: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  rank: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  rankText: { color: colors.ink, fontFamily: fonts.displaySemi, fontWeight: "800", fontSize: 16 },
  titleWrap: { flex: 1, gap: 3 },
  market: {
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.9,
    textTransform: "uppercase",
  },
  selection: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: -0.25,
  },
  right: { alignItems: "flex-end", gap: 4 },
  odds: {
    color: colors.gold,
    fontFamily: fonts.displaySemi,
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: -0.3,
  },
  rating: {
    backgroundColor: colors.gold,
    color: colors.background,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: radius.pill,
    overflow: "hidden",
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  confidence: {
    color: colors.white,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
  },
  vision: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
  },
  picked: {
    color: colors.goldBright,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.6,
  },
  reasoning: { ...type.body, color: colors.silver },
  tags: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  tag: {
    color: colors.muted,
    fontFamily: fonts.bodyBold,
    fontSize: 10,
    fontWeight: "700",
    borderColor: "rgba(255,255,255,0.12)",
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.pill,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  warningBox: {
    backgroundColor: colors.dangerDeep,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  warningText: { color: colors.danger, fontSize: 13, lineHeight: 18 },
  safer: { color: colors.success, fontSize: 13, fontFamily: fonts.bodyBold, fontWeight: "700" },
  live: { color: colors.info, fontSize: 13, lineHeight: 18, fontFamily: fonts.bodyBold, fontWeight: "700" },
  hedge: { color: colors.warning, fontSize: 13, lineHeight: 18, fontFamily: fonts.bodyBold, fontWeight: "700" },
  sourceLink: {
    alignSelf: "flex-start",
    borderColor: colors.info,
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.lg,
    paddingVertical: 10,
  },
  sourceText: {
    color: colors.info,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
});
