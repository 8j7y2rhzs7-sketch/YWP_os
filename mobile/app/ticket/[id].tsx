import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { PlayerPortrait } from "@/components/PlayerPortrait";
import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { SlipBuilder } from "@/components/SlipBuilder";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing, type } from "@/theme";
import type { LockCheck, Recommendation, SettleDayResponse, Ticket } from "@/types";

export default function TicketDetailScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { request } = useAuth();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [lock, setLock] = useState<LockCheck | null>(null);
  const [alternatives, setAlternatives] = useState<Recommendation[]>([]);
  const [pickerLegId, setPickerLegId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setTicket(await request<Ticket>(`/tickets/${id}`));
      try {
        setAlternatives(await request<Recommendation[]>(`/tickets/${id}/alternatives`));
      } catch {
        setAlternatives([]);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ticket failed to load");
    } finally {
      setLoading(false);
    }
  }, [id, request]);

  useEffect(() => {
    void load();
  }, [load]);

  async function lockCheck() {
    if (!id) return;
    setAction("lock");
    setError(null);
    try {
      const result = await request<LockCheck>(`/tickets/${id}/lock-check`, {
        method: "POST",
        body: JSON.stringify({ updates: [] }),
      });
      setLock(result);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Lock Check failed");
    } finally {
      setAction(null);
    }
  }

  async function place() {
    if (!id) return;
    setAction("place");
    setError(null);
    try {
      const result = await request<Ticket>(`/tickets/${id}/place`, { method: "POST" });
      setTicket(result);
      Alert.alert(
        "YWP OS",
        "Ticket marked placed. Sync scores after games finish, or grade process later.",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ticket could not be placed");
    } finally {
      setAction(null);
    }
  }

  async function syncScores() {
    if (!id) return;
    setAction("settle");
    setError(null);
    try {
      const settle = await request<SettleDayResponse>("/sports/settle-day", {
        method: "POST",
        body: "{}",
      });
      await load();
      const parts: string[] = [];
      if (settle.graded) parts.push(`${settle.graded} graded`);
      if (settle.pending) parts.push(`${settle.pending} waiting on finals`);
      if (settle.skipped) parts.push(`${settle.skipped} skipped`);
      if (settle.errors) parts.push(`${settle.errors} failed`);
      const detail = settle.items
        .slice(0, 5)
        .map((item) => `${item.selection || "ticket"}: ${item.detail || item.status}`)
        .join("\n");
      Alert.alert(
        "Score sync",
        parts.length
          ? `${parts.join(" · ")}${detail ? `\n\n${detail}` : ""}`
          : "No placed MLB legs were ready. Games must be Final first.",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Score sync failed");
    } finally {
      setAction(null);
    }
  }

  async function discardTicket() {
    if (!id) return;
    Alert.alert(
      "Discard this ticket?",
      "Use this for tickets that never locked or you are not placing. They leave the vault and cannot be graded.",
      [
        { text: "Keep", style: "cancel" },
        {
          text: "Discard",
          style: "destructive",
          onPress: () => {
            void (async () => {
              setAction("cancel");
              setError(null);
              try {
                await request(`/tickets/${id}/cancel`, { method: "POST" });
                router.replace("/(tabs)/tickets");
              } catch (reason) {
                setError(reason instanceof Error ? reason.message : "Could not discard ticket");
              } finally {
                setAction(null);
              }
            })();
          },
        },
      ],
    );
  }

  async function skipLeg(legId: string) {
    if (!id) return;
    setAction(legId);
    setError(null);
    try {
      setTicket(
        await request<Ticket>(`/tickets/${id}/legs/${legId}`, {
          method: "PATCH",
          body: JSON.stringify({
            action: "skip",
            skip_reason: "Removed as the weakest leg after final YWP review",
          }),
        }),
      );
      setLock(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Leg could not be skipped");
    } finally {
      setAction(null);
    }
  }

  async function restoreLeg(legId: string) {
    if (!id) return;
    setAction(legId);
    try {
      setTicket(
        await request<Ticket>(`/tickets/${id}/legs/${legId}`, {
          method: "PATCH",
          body: JSON.stringify({ action: "follow" }),
        }),
      );
      setLock(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Leg could not be restored");
    } finally {
      setAction(null);
    }
  }

  async function replaceLeg(legId: string, recommendationId: string) {
    if (!id) return;
    setAction(legId);
    try {
      setTicket(
        await request<Ticket>(`/tickets/${id}/legs/${legId}`, {
          method: "PATCH",
          body: JSON.stringify({
            action: "replace",
            replacement_recommendation_id: recommendationId,
          }),
        }),
      );
      setPickerLegId(null);
      setLock(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Replacement failed");
    } finally {
      setAction(null);
    }
  }

  async function addLeg(recommendationId: string) {
    if (!id) return;
    setAdding(true);
    try {
      setTicket(
        await request<Ticket>(`/tickets/${id}/legs`, {
          method: "POST",
          body: JSON.stringify({ recommendation_id: recommendationId }),
        }),
      );
      setPickerLegId(null);
      setLock(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not add that play");
    } finally {
      setAdding(false);
    }
  }

  if (loading) {
    return (
      <Screen>
        <LoadingState label="Loading ticket and exposure…" />
      </Screen>
    );
  }

  if (!ticket) {
    return (
      <Screen>
        <ErrorNotice message={error ?? "Ticket not found"} />
        <YwpButton label="BACK TO TICKETS" onPress={() => router.replace("/(tabs)/tickets")} />
      </Screen>
    );
  }

  const activeLegs = ticket.legs.filter((leg) => leg.action !== "skip");
  const canEdit = !["placed", "settled", "cancelled"].includes(ticket.status);

  return (
    <Screen sport={ticket.sport} refreshing={loading} onRefresh={() => void load()}>
      <BrandHeader title="LOCK CENTER" subtitle="EDIT • SWAP • FINAL SWEEP" compact sport={ticket.sport} />
      <MetalPanel tone={ticket.last_lock_status === "LOCKED" ? "success" : "gold"}>
        <View style={styles.header}>
          <View style={styles.flex}>
            <Text style={type.eyebrow}>{ticket.ticket_type.replaceAll("_", " ")}</Text>
            <Text style={styles.title}>{ticket.label}</Text>
            <Text style={type.caption}>
              {ticket.sport.toUpperCase()} • {ticket.slate_date} • {ticket.status.toUpperCase()}
            </Text>
          </View>
          <StatusPill value={ticket.last_lock_status ?? ticket.status} />
        </View>
        <View style={styles.metrics}>
          <Metric label="Stake" value={`$${ticket.stake}`} />
          <Metric label="Potential" value={`$${ticket.potential_payout}`} accent={colors.success} />
          <Metric label="Confidence" value={`${ticket.confidence_score}%`} />
          <Metric label="Risk" value={ticket.risk.toUpperCase()} accent={colors.warning} />
        </View>
        <Text style={type.caption}>
          A saved ticket is never permission to place it. Any lineup, starter,
          injury, price, weather, duration, correlation, or exposure change can
          block the lock.
        </Text>
      </MetalPanel>
      {error ? <ErrorNotice message={error} /> : null}

      <SectionTitle title="Ticket Legs" subtitle="Follow, remove the weakest leg, or replace from verified plays." />
      {ticket.legs.map((leg) => (
        <MetalPanel key={leg.id} tone={leg.action === "skip" ? "danger" : "default"}>
          <View style={styles.legRow}>
            <Text style={styles.number}>{leg.position}</Text>
            <PlayerPortrait
              imageUrl={leg.image_url}
              teamImageUrl={leg.team_image_url}
              sport={ticket.sport}
              size={44}
            />
            <View style={styles.flex}>
              <Text style={styles.selection}>{leg.selection}</Text>
              <Text style={type.caption}>
                {leg.action.toUpperCase()} • thesis {leg.thesis_key}
              </Text>
            </View>
            <Text style={styles.odds}>
              {leg.american_odds > 0 ? "+" : ""}
              {leg.american_odds}
            </Text>
          </View>
          {leg.skip_reason ? <Text style={styles.skipReason}>{leg.skip_reason}</Text> : null}
          {leg.outcome ? <StatusPill value={leg.outcome} /> : null}
          {canEdit && leg.action !== "skip" ? (
            <>
              <YwpButton
                label="SWAP THIS LEG"
                variant="outline"
                onPress={() => setPickerLegId(leg.id)}
              />
              <YwpButton
                label="REMOVE WEAKEST LEG"
                variant="danger"
                onPress={() => void skipLeg(leg.id)}
                loading={action === leg.id}
              />
            </>
          ) : null}
          {canEdit && leg.action === "skip" ? (
            <YwpButton
              label="PUT THIS LEG BACK"
              variant="outline"
              onPress={() => void restoreLeg(leg.id)}
              loading={action === leg.id}
            />
          ) : null}
          {ticket.status === "placed" && leg.action !== "skip" && !leg.outcome ? (
            <YwpButton
              label="GRADE RESULT & PROCESS"
              variant="outline"
              onPress={() => router.push(`/result/${leg.recommendation_id}`)}
            />
          ) : null}
          {ticket.status === "placed" || ticket.status === "settled"
            ? leg.outcome
              ? (
                  <Text style={type.caption}>
                    Result recorded. Open process grade anytime to complete the audit.
                  </Text>
                )
              : null
            : null}
        </MetalPanel>
      ))}

      {(ticket.status === "placed" || ticket.status === "settled") &&
      ticket.legs.some((leg) => leg.action !== "skip" && !leg.outcome) ? (
        <YwpButton
          label="SYNC SCORES & RESULTS"
          onPress={() => void syncScores()}
          loading={action === "settle"}
        />
      ) : null}

      {canEdit ? (
        <YwpButton
          label="ADD ANOTHER QUALIFIED PLAY"
          variant="outline"
          onPress={() => setPickerLegId("add")}
          disabled={!alternatives.length}
        />
      ) : null}

      {canEdit && activeLegs.length ? (
        <YwpButton
          label="RUN FINAL LOCK CHECK"
          onPress={() => void lockCheck()}
          loading={action === "lock"}
        />
      ) : null}

      {lock ? (
        <>
          <SectionTitle title="Lock Check Result" subtitle={`Valid until ${new Date(lock.expires_at).toLocaleTimeString()}`} />
          <MetalPanel tone={lock.lock_status === "LOCKED" ? "success" : "danger"}>
            <View style={styles.header}>
              <View style={styles.flex}>
                <StatusPill value={lock.lock_status} />
                <Text style={styles.title}>{lock.recommended_action.replaceAll("_", " ")}</Text>
              </View>
              <Text style={styles.lockScore}>{lock.ticket_confidence_score}</Text>
            </View>
            <Text style={type.body}>{lock.overall_message}</Text>
            {Object.entries(lock.checks).map(([key, value]) => (
              <View key={key} style={styles.checkRow}>
                <Text style={styles.checkName}>{key.replaceAll("_", " ")}</Text>
                <StatusPill value={value} />
              </View>
            ))}
            {lock.leg_results.map((result) => (
              <View key={result.recommendation_id} style={styles.resultBox}>
                <Text style={styles.selection}>{result.selection}</Text>
                <StatusPill value={result.status} />
                {result.changes_detected.map((change) => (
                  <Text key={change} style={type.caption}>• {change}</Text>
                ))}
              </View>
            ))}
          </MetalPanel>
        </>
      ) : null}

      {ticket.last_lock_status === "LOCKED" && ticket.status !== "placed" ? (
        <YwpButton label="MARK TICKET PLACED" variant="success" onPress={() => void place()} loading={action === "place"} />
      ) : null}
      {ticket.status !== "settled" && ticket.status !== "cancelled" ? (
        <YwpButton
          label={
            ["draft", "locked"].includes(ticket.status)
              ? "DISCARD STUCK TICKET"
              : "CANCEL TICKET"
          }
          variant="danger"
          onPress={() => void discardTicket()}
          loading={action === "cancel"}
        />
      ) : null}
      {["draft", "locked"].includes(ticket.status) ? (
        <Text style={type.caption}>
          Draft/locked tickets cannot sync scores. Discard ones that never locked,
          or finish Lock Check → Place if you still want them graded later.
        </Text>
      ) : null}
      {ticket.legs.length > 0 ? (
        <SlipBuilder
          ticketLabel={ticket.label}
          legs={ticket.legs.map((l) => ({
            selection: l.selection,
            american_odds: l.american_odds,
            thesis_key: l.thesis_key,
            status: l.action,
          }))}
          stake={String(ticket.stake)}
          potentialPayout={String(ticket.potential_payout)}
          lockStatus={ticket.last_lock_status}
        />
      ) : null}

      <Text style={styles.footer}>
        Lock Check refreshes MLB and sportsbook snapshots on the server before
        placement. Demo tickets may clear without a live provider pull.
      </Text>

      <Modal
        visible={pickerLegId !== null}
        transparent
        animationType="slide"
        onRequestClose={() => setPickerLegId(null)}
      >
        <Pressable style={styles.backdrop} onPress={() => setPickerLegId(null)}>
          <Pressable style={styles.modal} onPress={(event) => event.stopPropagation()}>
            <Text style={type.eyebrow}>
              {pickerLegId === "add" ? "ADD A QUALIFIED PLAY" : "SWAP THIS LEG"}
            </Text>
            <Text style={styles.modalTitle}>
              {pickerLegId === "add" ? "Build the ticket yourself" : "Replace from the same slate"}
            </Text>
            <Text style={type.caption}>
              Only plays that still pass gates. This is not a menu of every line on the board.
            </Text>
            <ScrollView style={styles.altList}>
              {alternatives.length ? (
                alternatives.map((alt) => (
                  <Pressable
                    key={alt.id}
                    style={styles.altRow}
                    onPress={() => {
                      void (async () => {
                        try {
                          if (pickerLegId === "add") await addLeg(alt.id);
                          else if (pickerLegId) await replaceLeg(pickerLegId, alt.id);
                        } catch (err) {
                          Alert.alert(
                            "Could not apply that play",
                            err instanceof Error ? err.message : "Try another.",
                          );
                        }
                      })();
                    }}
                  >
                    <PlayerPortrait
                      imageUrl={alt.image_url}
                      teamImageUrl={alt.team_image_url}
                      sport={alt.sport}
                      size={48}
                    />
                    <View style={styles.flex}>
                      <Text style={styles.selection}>{alt.selection}</Text>
                      <Text style={type.caption}>
                        {alt.event_name} • {alt.market_type.replaceAll("_", " ")}
                      </Text>
                    </View>
                    <Text style={styles.odds}>
                      {alt.american_odds > 0 ? "+" : ""}
                      {alt.american_odds}
                    </Text>
                  </Pressable>
                ))
              ) : (
                <Text style={type.body}>No other qualified plays remain on this slate.</Text>
              )}
            </ScrollView>
            <YwpButton label="CLOSE" variant="outline" onPress={() => setPickerLegId(null)} />
          </Pressable>
        </Pressable>
      </Modal>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1, gap: 3 },
  title: { color: colors.white, fontSize: 21, fontWeight: "900" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  legRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  number: {
    width: 34,
    height: 34,
    borderRadius: 17,
    lineHeight: 34,
    textAlign: "center",
    color: colors.background,
    backgroundColor: colors.gold,
    fontWeight: "900",
  },
  selection: { color: colors.white, fontSize: 15, fontWeight: "800" },
  odds: { color: colors.gold, fontSize: 16, fontWeight: "900" },
  skipReason: { color: colors.danger, fontSize: 12 },
  lockScore: { color: colors.gold, fontSize: 40, fontWeight: "900" },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
  },
  checkName: {
    flex: 1,
    color: colors.silver,
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase",
  },
  resultBox: {
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
    gap: spacing.sm,
  },
  footer: { ...type.caption, textAlign: "center", padding: spacing.md },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.78)",
    justifyContent: "flex-end",
  },
  modal: {
    width: "100%",
    maxHeight: "80%",
    backgroundColor: colors.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    borderColor: colors.borderGold,
    borderWidth: 1,
    padding: spacing.xl,
    gap: spacing.md,
  },
  modalTitle: { color: colors.white, fontSize: 22, fontWeight: "900" },
  altList: { maxHeight: 420 },
  altRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
});
