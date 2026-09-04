import { forwardRef } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { brandAssets } from "@/brandAssets";
import { brand, colors } from "@/theme";
import type { Readiness, TicketCard } from "@/types";

export type ShareTruthState =
  | "DEMO"
  | "RESEARCH_INCOMPLETE"
  | "DRAFT"
  | "VERIFIED"
  | "PASS"
  | "CUSTOM";

function resolveTruth(input: {
  card: TicketCard;
  readiness?: Readiness | null;
  protocolStatus?: string | null;
  isCustom?: boolean;
}): ShareTruthState {
  if (input.isCustom || input.card.key === "custom") return "CUSTOM";
  if (input.readiness === "DEMO") return "DEMO";
  if (input.card.legs.length === 0) return "PASS";
  if (input.readiness === "PARTIAL") return "RESEARCH_INCOMPLETE";
  if (input.protocolStatus === "DOUBLE_CLEARED" && input.readiness === "VERIFIED") {
    return "VERIFIED";
  }
  if (input.readiness === "VERIFIED") return "VERIFIED";
  return "DRAFT";
}

export const ShareCard = forwardRef<
  View,
  {
    card: TicketCard;
    slateDate: string;
    sport?: string;
    readiness?: Readiness | null;
    protocolStatus?: string | null;
    isCustom?: boolean;
  }
>(function ShareCard(
  { card, slateDate, sport = "MULTI", readiness, protocolStatus, isCustom },
  ref,
) {
  const truth = resolveTruth({ card, readiness, protocolStatus, isCustom });
  const isPass = truth === "PASS";
  const official =
    truth === "VERIFIED" && card.legs.length > 0 && !isCustom;

  const headerLine =
    truth === "DEMO"
      ? "YWP OS • DEMO BUILD — NOT LIVE EVIDENCE"
      : truth === "RESEARCH_INCOMPLETE"
        ? "YWP OS • RESEARCH INCOMPLETE"
        : truth === "CUSTOM"
          ? "YWP OS • CUSTOM CARD DRAFT"
          : truth === "VERIFIED"
            ? "YWP OS • VERIFIED-AS-OF THIS ANALYSIS"
            : truth === "PASS"
              ? "YWP OS • OFFICIAL PASS"
              : "YWP OS • DRAFT BOARD EXPORT";

  const statusLabel =
    truth === "DEMO"
      ? "DEMO • NOT OFFICIAL"
      : truth === "RESEARCH_INCOMPLETE"
        ? "PARTIAL • GATES OPEN"
        : truth === "CUSTOM"
          ? `${card.legs.length} CUSTOM LEG${card.legs.length === 1 ? "" : "S"}`
          : isPass
            ? "PASS • NO PLAY"
            : official
              ? `${card.legs.length} OFFICIAL ${card.legs.length === 1 ? "PLAY" : "PLAYS"}`
              : `${card.legs.length} DRAFT LEG${card.legs.length === 1 ? "" : "S"}`;

  const controlDefault =
    truth === "DEMO"
      ? "Demo fixtures cannot claim live verification."
      : truth === "RESEARCH_INCOMPLETE"
        ? "Missing research remains visible — not cleared."
        : truth === "CUSTOM"
          ? "Custom card uses backend risk metrics; not an auto-verified play."
          : official
            ? "Legs cleared gates in this analysis snapshot."
            : "Export reflects saved board state only.";

  return (
    <View ref={ref} style={styles.canvas} collapsable={false}>
      <LinearGradient
        colors={["#070A0F", "#0C121A", "#050608"]}
        style={StyleSheet.absoluteFill}
      />
      <View style={styles.cornerOne} />
      <View style={styles.cornerTwo} />
      <View style={styles.header}>
        <Image source={brandAssets.crest} style={styles.logo} resizeMode="contain" />
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>{brand.descriptor}</Text>
          <Text style={styles.protocol}>{headerLine}</Text>
        </View>
        <View style={styles.dateWrap}>
          <Text style={styles.date}>{slateDate}</Text>
          <Text style={styles.corrected}>PROTOCOL {brand.protocolVersion}</Text>
        </View>
      </View>

      <View style={styles.titleRow}>
        <View style={styles.titleCopy}>
          <Text style={styles.title}>{card.label.toUpperCase()}</Text>
          <Text style={styles.subtitle}>
            {sport.toUpperCase()} • CUSHION • VALUE • SCRIPT • MISS-BY-1
          </Text>
        </View>
        <View
          style={[
            styles.status,
            truth === "VERIFIED" || (!isPass && official)
              ? styles.statusSuccess
              : styles.statusDanger,
          ]}
        >
          <View
            style={[
              styles.dot,
              truth === "VERIFIED" || (!isPass && official)
                ? styles.dotSuccess
                : styles.dotDanger,
            ]}
          />
          <Text
            style={[
              styles.statusText,
              truth === "VERIFIED" || (!isPass && official)
                ? styles.successText
                : styles.dangerText,
            ]}
          >
            {statusLabel}
          </Text>
        </View>
      </View>
      <View style={styles.goldLine} />

      <View style={styles.legs}>
        {isPass ? (
          <View style={[styles.passBox, styles.dangerBorder]}>
            <Text style={styles.passEyebrow}>OFFICIAL YWP DECISION</Text>
            <Text style={styles.passTitle}>NO EDGE CLEARED EVERY GATE</Text>
            <Text style={styles.passBody}>
              No replacement leg. No forced parlay. Capital preservation wins.
            </Text>
          </View>
        ) : (
          card.legs.slice(0, 5).map((leg, index) => (
            <View key={leg.id} style={styles.leg}>
              <View style={styles.number}>
                <Text style={styles.numberText}>{index + 1}</Text>
              </View>
              <View style={styles.legCopy}>
                <Text style={styles.legMeta}>
                  {leg.sport.toUpperCase()} • {leg.edge_class.toUpperCase()} EDGE
                  {leg.event_name ? ` • ${leg.event_name}` : ""}
                </Text>
                <Text style={styles.selection}>{leg.selection.toUpperCase()}</Text>
                <Text style={styles.playTo}>
                  PLAY AT {leg.american_odds > 0 ? "+" : ""}
                  {leg.american_odds} • VISION {leg.vision_score}
                </Text>
              </View>
              <View style={styles.yis}>
                <Text style={styles.yisText}>YIS {leg.ywp_rating}</Text>
              </View>
            </View>
          ))
        )}
      </View>

      <View style={[styles.control, isPass || truth === "DEMO" ? styles.dangerBorder : styles.successBorder]}>
        <Text
          style={[
            styles.controlTitle,
            isPass || truth === "DEMO" ? styles.dangerText : styles.successText,
          ]}
        >
          FINAL CONTROL
        </Text>
        <Text style={styles.controlBody}>
          YWP SCORE {card.quality_score ?? card.confidence_score}/100 • RISK{" "}
          {card.risk.toUpperCase()} • NO FORCING
        </Text>
        <Text style={styles.controlBody}>
          {card.warnings[0] ?? controlDefault}
        </Text>
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerGold}>YWP OS • STRICT MODE • NO FORCING</Text>
        <Text style={styles.footerText}>WAGER RESPONSIBLY</Text>
      </View>
      <View style={styles.footerBottom}>
        <Text style={styles.footerBrand}>{brand.product}</Text>
        <Text style={styles.footerSlogan}>{brand.primaryLine}</Text>
        <Text style={styles.footerSlogan}>{brand.footer}</Text>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  canvas: {
    width: "100%",
    aspectRatio: 4 / 5,
    padding: 18,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.borderGold,
  },
  cornerOne: {
    position: "absolute",
    width: 180,
    height: 180,
    left: -90,
    bottom: -90,
    backgroundColor: "rgba(245,197,66,0.035)",
    transform: [{ rotate: "45deg" }],
  },
  cornerTwo: {
    position: "absolute",
    width: 160,
    height: 160,
    right: -90,
    top: -90,
    backgroundColor: "rgba(255,255,255,0.025)",
    transform: [{ rotate: "45deg" }],
  },
  header: { flexDirection: "row", alignItems: "center", gap: 10 },
  logo: { width: 46, height: 46, borderRadius: 23 },
  headerCopy: { flex: 1, gap: 3 },
  eyebrow: { color: colors.gold, fontSize: 8, fontWeight: "900", letterSpacing: 2 },
  protocol: { color: colors.silver, fontSize: 9, fontWeight: "700" },
  dateWrap: { alignItems: "flex-end", gap: 3 },
  date: { color: colors.silver, fontSize: 9, fontWeight: "900" },
  corrected: { color: colors.dim, fontSize: 7, fontWeight: "800" },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 12 },
  titleCopy: { flex: 1, gap: 4 },
  title: { color: colors.white, fontSize: 22, fontWeight: "900", letterSpacing: -0.4 },
  subtitle: { color: colors.muted, fontSize: 8, fontWeight: "700" },
  status: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    borderRadius: 99,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  statusSuccess: { borderColor: colors.success, backgroundColor: colors.successDeep },
  statusDanger: { borderColor: colors.danger, backgroundColor: colors.dangerDeep },
  dot: { width: 6, height: 6, borderRadius: 3 },
  dotSuccess: { backgroundColor: colors.success },
  dotDanger: { backgroundColor: colors.danger },
  statusText: { fontSize: 8, fontWeight: "900" },
  successText: { color: colors.success },
  dangerText: { color: colors.danger },
  goldLine: { height: 2, backgroundColor: colors.gold, marginTop: 10 },
  legs: { flex: 1, justifyContent: "center", gap: 7, paddingVertical: 10 },
  leg: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: "rgba(14,19,26,0.9)",
    borderRadius: 10,
    padding: 10,
  },
  number: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.gold,
    alignItems: "center",
    justifyContent: "center",
  },
  numberText: { color: colors.background, fontSize: 12, fontWeight: "900" },
  legCopy: { flex: 1, gap: 2 },
  legMeta: { color: colors.success, fontSize: 7, fontWeight: "900", letterSpacing: 1.4 },
  selection: { color: colors.white, fontSize: 12, fontWeight: "800" },
  playTo: { color: colors.gold, fontSize: 8, fontWeight: "900" },
  yis: {
    minWidth: 58,
    backgroundColor: colors.gold,
    borderRadius: 8,
    paddingHorizontal: 7,
    paddingVertical: 7,
    alignItems: "center",
  },
  yisText: { color: colors.background, fontSize: 8, fontWeight: "900" },
  passBox: { borderWidth: 2, borderRadius: 14, padding: 24, gap: 10 },
  passEyebrow: { color: colors.danger, fontSize: 9, fontWeight: "900", letterSpacing: 2 },
  passTitle: { color: colors.white, fontSize: 24, fontWeight: "900" },
  passBody: { color: colors.silver, fontSize: 13, lineHeight: 18 },
  control: { borderWidth: 2, borderRadius: 12, padding: 12, gap: 4 },
  successBorder: { borderColor: colors.success, backgroundColor: "rgba(9,57,37,0.65)" },
  dangerBorder: { borderColor: colors.danger, backgroundColor: "rgba(60,16,24,0.65)" },
  controlTitle: { fontSize: 9, fontWeight: "900", letterSpacing: 1.8 },
  controlBody: { color: colors.white, fontSize: 9, lineHeight: 13 },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingVertical: 9,
  },
  footerGold: { color: colors.gold, fontSize: 7, fontWeight: "900", letterSpacing: 1 },
  footerText: { color: colors.silver, fontSize: 7, fontWeight: "800" },
  footerBottom: { flexDirection: "row", justifyContent: "space-between", paddingTop: 8 },
  footerBrand: { color: colors.gold, fontSize: 8, fontWeight: "900" },
  footerSlogan: { color: colors.silver, fontSize: 7, fontWeight: "800" },
});
