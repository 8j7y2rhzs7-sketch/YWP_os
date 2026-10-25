import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { MetalPanel } from "@/components/MetalPanel";
import { SectionTitle } from "@/components/SectionTitle";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { colors, fonts, spacing, type } from "@/theme";
import type { LiveBoard, LivePlay } from "@/types";

const POLL_MS = 20_000;

function paceColor(pace: LivePlay["pace"]): string {
  if (pace === "cashing" || pace === "cashed") return colors.success;
  if (pace === "behind" || pace === "missed") return colors.danger;
  if (pace === "push") return colors.warning;
  return colors.muted;
}

function score(game: LiveBoard["games"][number]): string {
  if (game.away_score === null || game.home_score === null) return game.detail || "Not started";
  return `${game.away_score}–${game.home_score}`;
}

export function LiveStrip() {
  const { request } = useAuth();
  const [board, setBoard] = useState<LiveBoard | null>(null);

  const load = useCallback(async () => {
    try {
      setBoard(await request<LiveBoard>("/live"));
    } catch {
      setBoard(null);
    }
  }, [request]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!board || board.live_count < 1) return;
    const timer = setInterval(() => {
      void load();
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [board, load]);

  const games = (board?.games ?? []).filter((game) => game.status === "LIVE").slice(0, 2);
  const plays = (board?.plays ?? [])
    .filter((play) => play.pace === "cashing" || play.pace === "behind")
    .slice(0, 2);

  return (
    <View>
      <SectionTitle
        title="Live"
        subtitle={
          board?.live_count
            ? `${board.live_count} game${board.live_count === 1 ? "" : "s"} on now`
            : "Scores and how plays are tracking."
        }
      />
      <MetalPanel>
        {plays.map((play) => (
          <View key={play.id} style={styles.row}>
            <View style={styles.copy}>
              <Text style={styles.title} numberOfLines={1}>
                {play.selection}
              </Text>
              <Text style={type.caption} numberOfLines={1}>
                {play.stat_label ?? play.detail}
              </Text>
            </View>
            <Text style={[styles.pace, { color: paceColor(play.pace) }]}>{play.pace}</Text>
          </View>
        ))}
        {games.map((game) => (
          <View key={`${game.sport}-${game.event_id}`} style={styles.row}>
            <View style={styles.copy}>
              <Text style={styles.title} numberOfLines={1}>
                {game.away_team} at {game.home_team}
              </Text>
              <Text style={type.caption}>{game.detail}</Text>
            </View>
            <Text style={styles.score}>{score(game)}</Text>
          </View>
        ))}
        {!plays.length && !games.length ? (
          <Text style={type.body}>No games in progress. The board is still here to check.</Text>
        ) : null}
        <YwpButton label="Open live" onPress={() => router.push("/live")} />
      </MetalPanel>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  copy: { flex: 1, gap: 2 },
  title: {
    color: colors.white,
    fontFamily: fonts.bodyBold,
    fontSize: 15,
    fontWeight: "700",
  },
  pace: {
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  score: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 16,
    fontWeight: "700",
  },
});
