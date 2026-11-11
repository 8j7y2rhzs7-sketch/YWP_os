import { router } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Modal, Pressable, StyleSheet, Switch, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { RecommendationCard } from "@/components/RecommendationCard";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { StatusPill } from "@/components/StatusPill";
import { TicketCardView } from "@/components/TicketCardView";
import { YwpButton } from "@/components/YwpButton";
import { useAppData } from "@/context/AppDataContext";
import { useAuth } from "@/context/AuthContext";
import { colors, radius, spacing, type } from "@/theme";
import type { ReadyBoard, Recommendation, Ticket, TicketCard } from "@/types";

const cardOrder = [
  "max_bet",
  "elite_two",
  "core_3",
  "core_4",
  "core_5",
  "core_parlay",
  "cash_builder",
  "edge_plays",
  "fortress",
  "handicap",
  "no_stress",
  "scripted",
  "quick_cash",
  "chain_reaction",
  "ghostt",
  "comeback",
  "ticket_a",
  "ticket_b",
  "ticket_c",
];

const crossOrder = ["cross_2", "cross_3", "cross_board"];

function formatWhen(value?: string | null): string {
  if (!value) return "when the board is ready";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function ReadyScreen() {
  const { request } = useAuth();
  const { saveBuild } = useAppData();
  const [board, setBoard] = useState<ReadyBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCard, setSelectedCard] = useState<TicketCard | null>(null);
  const [stake, setStake] = useState("10.00");
  const [saving, setSaving] = useState(false);
  const [intentionalCorrelation, setIntentionalCorrelation] = useState(false);
  const [intentionalThesis, setIntentionalThesis] = useState(false);
  const [selectedPickIds, setSelectedPickIds] = useState<string[]>([]);
  const [customCard, setCustomCard] = useState<TicketCard | null>(null);
  const [customPreviewBusy, setCustomPreviewBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const next = await request<ReadyBoard>("/sports/ready-board");
      setBoard(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ready board failed to load");
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!board) return;
    if (board.status === "priced" || board.status === "missed" || board.status === "no_games") {
      return;
    }
    const timer = setInterval(() => {
      void load();
    }, 20_000);
    return () => clearInterval(timer);
  }, [board, load]);

  const plays = board?.plays ?? [];
  const groups = useMemo(() => {
    const map = new Map<string, Recommendation[]>();
    for (const play of plays) {
      const key = play.sport.toUpperCase();
      map.set(key, [...(map.get(key) ?? []), play]);
    }
    return [...map.entries()];
  }, [plays]);

  const orderedCards = useMemo(
    () =>
      cardOrder
        .map((key) => board?.cards[key])
        .filter((card): card is TicketCard => Boolean(card)),
    [board],
  );
  const crossCards = useMemo(
    () =>
      crossOrder
        .map((key) => board?.cross_parlays[key])
        .filter((card): card is TicketCard => Boolean(card)),
    [board],
  );
  const customLegs = useMemo(
    () => plays.filter((item) => selectedPickIds.includes(item.id)),
    [plays, selectedPickIds],
  );

  useEffect(() => {
    if (!customLegs.length) {
      setCustomCard(null);
      return;
    }
    let cancelled = false;
    const ids = customLegs.map((item) => item.id);
    setCustomPreviewBusy(true);
    void (async () => {
      try {
        const preview = await request<TicketCard>("/sports/preview-custom-card", {
          method: "POST",
          body: JSON.stringify({
            recommendation_ids: ids,
            label: `Custom ${ids.length}-${ids.length === 1 ? "leg" : "legs"}`,
          }),
        });
        if (!cancelled) setCustomCard(preview);
      } catch {
        if (!cancelled) {
          setCustomCard(null);
          setError("Custom card metrics unavailable — retry the selection.");
        }
      } finally {
        if (!cancelled) setCustomPreviewBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [customLegs, request]);

  function togglePick(id: string) {
    setSelectedPickIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  function openTicketComposer(card: TicketCard) {
    setError(null);
    setIntentionalCorrelation(false);
    setIntentionalThesis(false);
    setSelectedCard(card);
  }

  async function saveTicket() {
    if (!selectedCard || !board?.analysis_id) return;
    const numericStake = Number(stake);
    if (!Number.isFinite(numericStake) || numericStake <= 0) {
      setError("Enter a valid stake amount greater than 0");
      return;
    }
    if (!selectedCard.legs.length) {
      setError("Select at least one approved play before saving");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const ticket = await request<Ticket>("/tickets", {
        method: "POST",
        body: JSON.stringify({
          ticket_type: selectedCard.key,
          label: selectedCard.label,
          recommendation_ids: selectedCard.recommendation_ids,
          stake: numericStake.toFixed(2),
          intentional_correlation: intentionalCorrelation,
          intentional_thesis_exposure: intentionalThesis,
          override_acknowledged: false,
        }),
      });
      saveBuild(board.analysis_id, {
        analysis_id: board.analysis_id,
        official_pass: false,
        cards: { ...board.cards, ...board.cross_parlays, [selectedCard.key]: selectedCard },
        stay_away: [],
        quarantined: [],
      });
      setSelectedCard(null);
      router.push(`/ticket/${ticket.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ticket could not be saved");
    } finally {
      setSaving(false);
    }
  }

  if (loading && !board) {
    return (
      <Screen>
        <LoadingState label="Checking the plays that were already approved…" />
      </Screen>
    );
  }

  const waiting = board?.status !== "priced";

  return (
    <Screen sport={plays[0]?.sport}>
      <BrandHeader
        title="READY PLAYS"
        subtitle="ALREADY APPROVED • CROSS-SPORT PARLAYS"
        compact
        sport={plays[0]?.sport}
      />
      <MetalPanel tone={board?.status === "priced" ? "gold" : "default"}>
        <View style={styles.summaryTop}>
          <View style={styles.flex}>
            <Text style={type.eyebrow}>BEFORE YOU TAP RUN</Text>
            <Text style={styles.title}>
              {board?.status === "priced" ? "The list is already here." : "The board is still cooking."}
            </Text>
          </View>
          <StatusPill value={(board?.status ?? "idle").replace(/_/g, " ").toUpperCase()} />
        </View>
        <Text style={type.body}>{board?.notice}</Text>
        <View style={styles.metrics}>
          <Metric label="Approved" value={plays.length} accent={colors.success} />
          <Metric label="Sports" value={groups.length} />
          <Metric label="Priced pull" value={formatWhen(board?.pull2_at)} />
          <Metric
            label="Lead"
            value={board?.lead_minutes ? `${board.lead_minutes}m` : "—"}
            accent={colors.gold}
          />
        </View>
        <Text style={type.caption}>
          Matchups come in at the start of the Eastern day. One priced pull runs before the
          first game, and that lead moves when past boards were early or late. Run is still
          there if you want a fresh slate.
        </Text>
      </MetalPanel>
      {!selectedCard && error ? <ErrorNotice message={error} /> : null}

      {waiting ? (
        <>
          <SectionTitle
            title="Today's matchups"
            subtitle="Times only. Prices land on the learned pull, or when you Run."
          />
          {board?.games.length ? (
            board.games.map((game) => (
              <MetalPanel key={`${game.sport}-${game.event_id}`}>
                <View style={styles.summaryTop}>
                  <View style={styles.flex}>
                    <Text style={styles.ticketTitle}>{game.event_name}</Text>
                    <Text style={type.caption}>{formatWhen(game.commence_time)}</Text>
                  </View>
                  <StatusPill value={game.sport.toUpperCase()} />
                </View>
              </MetalPanel>
            ))
          ) : (
            <MetalPanel>
              <Text style={type.body}>No matchups stored yet. This page refreshes on its own.</Text>
            </MetalPanel>
          )}
          <YwpButton label="RUN IT YOURSELF" variant="outline" onPress={() => router.push("/(tabs)/slate")} />
        </>
      ) : null}

      <SectionTitle
        title="Approved plays"
        subtitle="PLAY and LEAN from each sport. Tap any of them to build your own ticket."
      />
      {groups.length ? (
        groups.map(([sport, items]) => (
          <View key={sport} style={styles.group}>
            <Text style={type.eyebrow}>{sport}</Text>
            {items.map((item) => (
              <RecommendationCard
                key={item.id}
                item={item}
                selected={selectedPickIds.includes(item.id)}
                onPress={
                  ["PLAY", "LEAN"].includes(item.decision) ? () => togglePick(item.id) : undefined
                }
              />
            ))}
          </View>
        ))
      ) : (
        <MetalPanel>
          <StatusPill value={waiting ? "WAITING" : "PASS"} />
          <Text style={styles.title}>
            {waiting ? "Approved plays are not in yet." : "No play cleared the gates."}
          </Text>
          <Text style={type.body}>
            {waiting
              ? "The list shows up here when the priced pull finishes. You can still Run."
              : "PASS is the result. Nothing on this screen was filled in to make a ticket."}
          </Text>
        </MetalPanel>
      )}
      {customLegs.length ? (
        <YwpButton
          label={
            customPreviewBusy
              ? "LOADING CUSTOM CARD METRICS…"
              : customCard
                ? `SAVE CUSTOM ${customLegs.length}-LEG TICKET`
                : "CUSTOM METRICS UNAVAILABLE"
          }
          onPress={() => customCard && openTicketComposer(customCard)}
          loading={customPreviewBusy}
        />
      ) : plays.length ? (
        <Text style={type.caption}>
          Tap approved plays to mix your own ticket, including across sports. Or open a
          recommended card below.
        </Text>
      ) : null}

      <SectionTitle
        title="Cross-sport parlays"
        subtitle="One approved play from each sport. Same-game stacks are not recommended here."
      />
      {crossCards.length ? (
        crossCards.map((card) => (
          <TicketCardView
            key={card.key}
            card={card}
            onPress={card.legs.length ? () => openTicketComposer(card) : undefined}
          />
        ))
      ) : (
        <MetalPanel>
          <Text style={styles.title}>No cross-sport parlay yet.</Text>
          <Text style={type.body}>
            A recommendation shows up when at least two sports each have an approved play
            with enough cushion to stack.
          </Text>
        </MetalPanel>
      )}

      <SectionTitle
        title="Card buttons"
        subtitle="Same set as the decision board: Max Bet, Elite 2, cores, cash, and the rest."
      />
      {orderedCards.length ? (
        orderedCards.map((card) => (
          <TicketCardView
            key={card.key}
            card={card}
            onPress={card.legs.length ? () => openTicketComposer(card) : undefined}
          />
        ))
      ) : (
        <MetalPanel>
          <Text style={type.body}>
            Official cards stay empty when the gates refuse filler legs. Custom selection
            above still works from any approved play.
          </Text>
        </MetalPanel>
      )}

      <YwpButton label="RUN A FRESH SLATE" variant="outline" onPress={() => router.push("/(tabs)/slate")} />

      <Modal
        visible={Boolean(selectedCard)}
        transparent
        animationType="slide"
        onRequestClose={() => {
          setSelectedCard(null);
          setError(null);
        }}
      >
        <View style={styles.backdrop}>
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={() => {
              setSelectedCard(null);
              setError(null);
            }}
            accessibilityLabel="Dismiss ticket composer"
          />
          <View style={styles.modal}>
            <Text style={type.eyebrow}>SAVE DRAFT TICKET</Text>
            <Text style={styles.modalTitle}>{selectedCard?.label}</Text>
            <Text style={type.caption}>
              Saving is not placement. Lock Check is still mandatory immediately before any wager.
            </Text>
            {error ? <ErrorNotice message={error} /> : null}
            {error?.toLowerCase().includes("intentional_correlation") ||
            error?.toLowerCase().includes("correlated") ? (
              <Text style={type.caption}>Turn on Intentional correlation below, then save again.</Text>
            ) : null}
            <FormField
              label="Stake"
              value={stake}
              onChangeText={setStake}
              keyboardType="decimal-pad"
              placeholder="10.00"
            />
            <View style={styles.switchRow}>
              <View style={styles.flex}>
                <Text style={styles.switchTitle}>Intentional correlation</Text>
                <Text style={type.caption}>Only enable when the shared script is deliberate.</Text>
              </View>
              <Switch
                value={intentionalCorrelation}
                onValueChange={setIntentionalCorrelation}
                trackColor={{ false: colors.border, true: colors.goldDark }}
                thumbColor={intentionalCorrelation ? colors.gold : colors.silver}
              />
            </View>
            <View style={styles.switchRow}>
              <View style={styles.flex}>
                <Text style={styles.switchTitle}>Cross-ticket thesis exposure</Text>
                <Text style={type.caption}>Declared exposure remains subject to bankroll caps.</Text>
              </View>
              <Switch
                value={intentionalThesis}
                onValueChange={setIntentionalThesis}
                trackColor={{ false: colors.border, true: colors.goldDark }}
                thumbColor={intentionalThesis ? colors.gold : colors.silver}
              />
            </View>
            <YwpButton
              label="SAVE & OPEN LOCK CENTER"
              onPress={() => void saveTicket()}
              loading={saving}
              disabled={!selectedCard?.legs.length || saving}
            />
            <YwpButton
              label="CANCEL"
              variant="danger"
              onPress={() => {
                setSelectedCard(null);
                setError(null);
              }}
            />
          </View>
        </View>
      </Modal>
    </Screen>
  );
}

const styles = StyleSheet.create({
  summaryTop: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1, gap: spacing.xs },
  title: { color: colors.white, fontSize: 20, fontWeight: "900" },
  ticketTitle: { color: colors.white, fontSize: 16, fontWeight: "800" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  group: { gap: spacing.sm },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.78)",
    justifyContent: "flex-end",
  },
  modal: {
    width: "100%",
    maxWidth: 720,
    alignSelf: "center",
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg,
    borderColor: colors.borderGold,
    borderWidth: 1,
    padding: spacing.xl,
    gap: spacing.md,
  },
  modalTitle: { color: colors.white, fontSize: 24, fontWeight: "900" },
  switchRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  switchTitle: { color: colors.white, fontSize: 14, fontWeight: "800" },
});
