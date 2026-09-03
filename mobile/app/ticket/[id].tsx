import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing, type } from "@/theme";
import type { LockCheck, Ticket } from "@/types";

export default function TicketDetailScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { request } = useAuth();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [lock, setLock] = useState<LockCheck | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setTicket(await request<Ticket>(`/tickets/${id}`));
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
      Alert.alert("YWP OS", "Ticket marked placed. Grade each result honestly after settlement.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ticket could not be placed");
    } finally {
      setAction(null);
    }
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
    <Screen refreshing={loading} onRefresh={() => void load()}>
      <BrandHeader title="LOCK CENTER" subtitle="FINAL SWEEP • NO ASSUMPTIONS" compact />
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
            <YwpButton
              label="REMOVE WEAKEST LEG"
              variant="danger"
              onPress={() => void skipLeg(leg.id)}
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
        </MetalPanel>
      ))}

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
      <Text style={styles.footer}>
        Live-provider tickets require fresh current-state updates from the server.
        Empty updates are accepted only for clearly labeled demo data.
      </Text>
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
});
