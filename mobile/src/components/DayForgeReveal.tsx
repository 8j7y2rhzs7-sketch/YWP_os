import { useEffect, useRef } from "react";
import {
  Animated,
  Easing,
  Image,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
  Vibration,
  useWindowDimensions,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { brandAssets } from "@/brandAssets";
import { MetalShimmer } from "@/components/MetalShimmer";
import { PlayerPortrait } from "@/components/PlayerPortrait";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors, fonts, radius, spacing, type } from "@/theme";
import type { DayForgeResponse, Recommendation } from "@/types";

function oddsLabel(value: number): string {
  return value > 0 ? `+${value}` : String(value);
}

function PlayRevealCard({ play }: { play: Recommendation }) {
  return (
    <LinearGradient
      colors={["#3C2C0A", "#122030", "#071018"]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      style={styles.card}
    >
      <View style={styles.cardTop}>
        <PlayerPortrait
          imageUrl={play.image_url}
          teamImageUrl={play.team_image_url}
          sport={play.sport}
        />
        <View style={styles.cardCopy}>
          <Text style={styles.market}>
            {play.sport.toUpperCase()} · {play.market_type.replaceAll("_", " ")}
          </Text>
          <Text style={styles.selection}>{play.selection}</Text>
          <Text style={type.caption}>{play.event_name}</Text>
        </View>
        <StatusPill value={play.decision} />
      </View>

      <View style={styles.metrics}>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>ODDS</Text>
          <Text style={styles.metricValue}>{oddsLabel(play.american_odds)}</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>QUALITY</Text>
          <Text style={styles.metricValue}>{play.confidence_score}</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>YIS</Text>
          <Text style={styles.metricValue}>{Number(play.ywp_rating).toFixed(1)}</Text>
        </View>
        <View style={styles.metric}>
          <Text style={styles.metricLabel}>EDGE</Text>
          <Text style={[styles.metricValue, { color: colors.success }]}>
            {(Number(play.edge) * 100).toFixed(1)}%
          </Text>
        </View>
      </View>

      <Text style={styles.reason} numberOfLines={4}>
        {play.reasoning_summary}
      </Text>
      <Text style={styles.disclaimer}>
        Process play in the cash band — not a guarantee. Lock Check before you place.
      </Text>
    </LinearGradient>
  );
}

/**
 * Full-screen high-res vault reveal when Day Forge finishes cooking.
 */
export function DayForgeReveal({
  visible,
  forge,
  onClose,
  onRunProtocol,
}: {
  visible: boolean;
  forge: DayForgeResponse | null;
  onClose: () => void;
  onRunProtocol?: () => void;
}) {
  const reduceMotion = useReduceMotion();
  const { height } = useWindowDimensions();
  const blast = useRef(new Animated.Value(0)).current;
  const door = useRef(new Animated.Value(0)).current;
  const card = useRef(new Animated.Value(0)).current;
  const spin = useRef(new Animated.Value(0)).current;
  const play = forge?.play ?? null;
  const isPass = forge?.status === "pass";

  useEffect(() => {
    if (!visible) {
      blast.setValue(0);
      door.setValue(0);
      card.setValue(0);
      spin.setValue(0);
      return;
    }
    if (!reduceMotion) {
      Vibration.vibrate([0, 40, 60, 80]);
    }
    if (reduceMotion) {
      blast.setValue(1);
      door.setValue(1);
      card.setValue(1);
      return;
    }
    blast.setValue(0);
    door.setValue(0);
    card.setValue(0);
    spin.setValue(0);

    Animated.sequence([
      Animated.timing(blast, {
        toValue: 1,
        duration: 520,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.parallel([
        Animated.spring(door, {
          toValue: 1,
          friction: 7,
          tension: 58,
          useNativeDriver: true,
        }),
        Animated.timing(spin, {
          toValue: 1,
          duration: 1400,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),
      Animated.spring(card, {
        toValue: 1,
        friction: 8,
        tension: 64,
        useNativeDriver: true,
      }),
    ]).start();
  }, [blast, card, door, reduceMotion, spin, visible]);

  const emblemScale = door.interpolate({
    inputRange: [0, 1],
    outputRange: [0.55, 1],
  });
  const emblemRotate = spin.interpolate({
    inputRange: [0, 1],
    outputRange: ["-12deg", "0deg"],
  });
  const flashOpacity = blast.interpolate({
    inputRange: [0, 0.35, 1],
    outputRange: [0, 0.85, 0],
  });
  const cardY = card.interpolate({
    inputRange: [0, 1],
    outputRange: [48, 0],
  });

  return (
    <Modal visible={visible} animationType="fade" transparent onRequestClose={onClose}>
      <View style={[styles.backdrop, { minHeight: height }]}>
        <LinearGradient
          colors={["rgba(2,5,10,0.96)", "rgba(8,18,28,0.98)", "rgba(18,12,4,0.96)"]}
          style={StyleSheet.absoluteFill}
        />
        <Animated.View
          pointerEvents="none"
          style={[
            styles.flash,
            {
              opacity: flashOpacity,
            },
          ]}
        />

        <Pressable style={styles.closeHit} onPress={onClose}>
          <Text style={styles.close}>CLOSE</Text>
        </Pressable>

        <Animated.View
          style={[
            styles.emblemWrap,
            {
              opacity: door,
              transform: [{ scale: emblemScale }, { rotate: emblemRotate }],
            },
          ]}
        >
          <Image
            source={isPass ? brandAssets.dayForgeSealed : brandAssets.dayForgeOpen}
            style={styles.emblem}
            resizeMode="contain"
          />
        </Animated.View>

        <MetalShimmer intensity="bright" periodMs={1600} style={styles.titleShimmer}>
          <Text style={styles.headline}>
            {isPass ? "FORGE PASS" : "DAY FORGE READY"}
          </Text>
        </MetalShimmer>
        <Text style={styles.subhead}>
          {forge?.notification_body ??
            forge?.message ??
            "One process play when the data clears — never forced juice."}
        </Text>

        <Animated.View
          style={{
            width: "100%",
            opacity: card,
            transform: [{ translateY: cardY }],
          }}
        >
          {play ? <PlayRevealCard play={play} /> : null}
          {isPass ? (
            <LinearGradient colors={["#2A1218", "#0A1018"]} style={styles.passPanel}>
              <Text style={styles.passTitle}>NO PLAY FORCED</Text>
              <Text style={styles.passBody}>
                The vault stayed closed. Nothing in the cash band cleared AIN + edge
                gates — YWP does not manufacture action.
              </Text>
            </LinearGradient>
          ) : null}
        </Animated.View>

        <View style={styles.actions}>
          {play ? (
            <YwpButton
              label="RUN FULL PROTOCOL"
              onPress={() => {
                onClose();
                onRunProtocol?.();
              }}
            />
          ) : null}
          <YwpButton label="HOLD" variant="outline" onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
  },
  flash: {
    ...StyleSheet.absoluteFill,
    backgroundColor: colors.goldBright,
  },
  closeHit: {
    position: "absolute",
    top: 54,
    right: 22,
    zIndex: 4,
    padding: 8,
  },
  close: {
    color: colors.silver,
    fontFamily: fonts.bodyBold,
    letterSpacing: 1.4,
    fontSize: 12,
  },
  emblemWrap: {
    width: 220,
    height: 220,
    marginBottom: spacing.sm,
  },
  emblem: {
    width: "100%",
    height: "100%",
  },
  titleShimmer: {
    alignSelf: "center",
  },
  headline: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 28,
    letterSpacing: 1.2,
    textAlign: "center",
  },
  subhead: {
    ...type.body,
    color: colors.silver,
    textAlign: "center",
    marginBottom: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  card: {
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(240,193,74,0.45)",
    padding: spacing.lg,
    gap: spacing.md,
  },
  cardTop: {
    flexDirection: "row",
    gap: spacing.md,
    alignItems: "center",
  },
  cardCopy: {
    flex: 1,
    gap: 2,
  },
  market: {
    color: colors.circuitBlueBright,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    letterSpacing: 0.8,
  },
  selection: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 20,
    letterSpacing: -0.3,
  },
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  metric: {
    width: "23%",
    minWidth: 68,
    backgroundColor: "rgba(0,0,0,0.28)",
    borderRadius: radius.md,
    paddingVertical: 8,
    paddingHorizontal: 6,
  },
  metricLabel: {
    color: colors.dim,
    fontFamily: fonts.bodyBold,
    fontSize: 9,
    letterSpacing: 0.8,
  },
  metricValue: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 16,
    marginTop: 2,
  },
  reason: {
    ...type.caption,
    color: colors.silver,
    lineHeight: 16,
  },
  disclaimer: {
    color: colors.dim,
    fontFamily: fonts.bodyMedium,
    fontSize: 11,
  },
  passPanel: {
    borderRadius: radius.xl,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(255,77,106,0.35)",
    gap: spacing.sm,
  },
  passTitle: {
    color: colors.danger,
    fontFamily: fonts.display,
    fontSize: 18,
  },
  passBody: {
    ...type.body,
    color: colors.silver,
  },
  actions: {
    width: "100%",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
});
