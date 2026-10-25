import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { useAuth } from "@/context/AuthContext";
import { colors, fonts, spacing, type } from "@/theme";
import type { LiveBoard, LiveGame, LivePlay } from "@/types";

const POLL_MS = 20_000;

function paceColor(pace: LivePlay["pace"]): string {
  if (pace === "cashing" || pace === "cashed") return colors.success;
  if (pace === "behind" || pace === "missed") return colors.danger;
  if (pace === "push") return colors.warning;
  return colors.muted;
}

function gameScore(game: LiveGame): string {
  if (game.away_score === null || game.home_score === null) return "—";
  return `${game.away_score}–${game.home_score}`;
}

export default function LiveScreen() {
  const { request } = useAuth();
  const [board, setBoard] = useState<LiveBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setBoard(await request<LiveBoard>("/live"));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Live board failed to load");
    } finally {
      setLoading(false);
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

  if (loading) {
    return (
      <Screen>
        <LoadingState label="Checking scores…" />
      </Screen>
    );
  }

  const yours = (board?.plays ?? []).filter((play) => play.source === "yours");
  const listed = (board?.plays ?? []).filter((play) => play.source === "board");

  return (
    <Screen refreshing={false} onRefresh={() => void load()}>
      {error ? <ErrorNotice message={error} /> : null}
      <Text style={styles.notice}>{board?.notice}</Text>

      <SectionTitle title="Your plays" subtitle="How the ones you saved are tracking." />
      {yours.length ? (
        yours.map((play) => <PlayRow key={play.id} play={play} />)
      ) : (
        <MetalPanel>
          <Text style={type.body}>No open ticket yet. The board below is still trackable.</Text>
        </MetalPanel>
      )}

      {listed.length ? (
        <>
          <SectionTitle title="Board" subtitle="Approved plays, even if you did not bet them." />
          {listed.map((play) => (
            <PlayRow key={play.id} play={play} />
          ))}
        </>
      ) : null}

      <SectionTitle title="Major games" subtitle="NBA, NFL, NHL, MLB, and college football." />
      {(board?.games ?? []).map((game) => (
        <MetalPanel key={`${game.sport}-${game.event_id}`}>
          <View style={styles.row}>
            <View style={styles.copy}>
              <Text style={styles.sport}>{game.sport.toUpperCase()}</Text>
              <Text style={styles.title}>
                {game.away_team} at {game.home_team}
              </Text>
              <Text style={type.caption}>{game.detail}</Text>
            </View>
            <Text style={styles.score}>{gameScore(game)}</Text>
          </View>
        </MetalPanel>
      ))}
      {!board?.games.length ? (
        <MetalPanel>
          <Text style={type.body}>No major games on the board for this slate.</Text>
        </MetalPanel>
      ) : null}
    </Screen>
  );
}

function PlayRow({ play }: { play: LivePlay }) {
  return (
    <MetalPanel>
      <View style={styles.row}>
        <View style={styles.copy}>
          <Text style={styles.title}>{play.selection}</Text>
          <Text style={type.caption}>
            {play.event_name}
            {play.stat_label ? ` · ${play.stat_label}` : ""}
          </Text>
          {play.detail ? <Text style={type.caption}>{play.detail}</Text> : null}
        </View>
        <Text style={[styles.pace, { color: paceColor(play.pace) }]}>{play.pace}</Text>
      </View>
    </MetalPanel>
  );
}

const styles = StyleSheet.create({
  notice: {
    ...type.caption,
    color: colors.dim,
    paddingTop: spacing.md,
  },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  copy: { flex: 1, gap: 2 },
  sport: {
    color: colors.muted,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.8,
  },
  title: {
    color: colors.white,
    fontFamily: fonts.bodyBold,
    fontSize: 16,
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
    fontSize: 20,
    fontWeight: "700",
  },
});
