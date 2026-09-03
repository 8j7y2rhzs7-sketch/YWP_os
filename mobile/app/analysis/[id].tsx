import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";

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
import type { BuildTicketResponse, Ticket, TicketCard } from "@/types";

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

export default function AnalysisScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { request } = useAuth();
  const { analyses, builds, saveBuild } = useAppData();
  const analysis = id ? analyses[id] : undefined;
  const build = id ? builds[id] : undefined;
  const [loading, setLoading] = useState(!build);
  const [error, setError] = useState<string | null>(null);
  const [selectedCard, setSelectedCard] = useState<TicketCard | null>(null);
  const [stake, setStake] = useState("10.00");
  const [saving, setSaving] = useState(false);
  const [intentionalCorrelation, setIntentionalCorrelation] = useState(false);
  const [intentionalThesis, setIntentionalThesis] = useState(false);
  const [selectedPickIds, setSelectedPickIds] = useState<string[]>([]);

  const runBuilder = useCallback(async () => {
    if (!id || !analysis) return;
    setLoading(true);
    setError(null);
    try {
      const response = await request<BuildTicketResponse>("/sports/build-ticket", {
        method: "POST",
        body: JSON.stringify({
          analysis_id: id,
          max_legs: 5,
          min_rating: 6.5,
          risk_profile: "balanced",
          exclude_correlated_unless_intentional: true,
        }),
      });
      saveBuild(id, response);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ticket Builder failed");
    } finally {
      setLoading(false);
    }
  }, [analysis, id, request, saveBuild]);

  useEffect(() => {
    if (!build) void runBuilder();
  }, [build, runBuilder]);

  const orderedCards = useMemo(
    () =>
      cardOrder
        .map((key) => build?.cards[key])
        .filter((card): card is TicketCard => Boolean(card)),
    [build],
  );

  const customLegs = useMemo(
    () =>
      (analysis?.ranked_picks ?? []).filter((item) => selectedPickIds.includes(item.id)),
    [analysis, selectedPickIds],
  );

  const customCard = useMemo<TicketCard | null>(() => {
    if (!customLegs.length) return null;
    const riskOrder = ["low", "medium", "medium_high", "high"];
    const risk = customLegs.reduce(
      (worst, item) =>
        riskOrder.indexOf(item.risk) > riskOrder.indexOf(worst) ? item.risk : worst,
      customLegs[0].risk,
    );
    return {
      key: "custom",
      label: `Custom ${customLegs.length}-leg`,
      recommendation_ids: customLegs.map((item) => item.id),
      legs: customLegs,
      risk,
      confidence_score: Math.round(
        customLegs.reduce((sum, item) => sum + item.confidence_score, 0) / customLegs.length,
      ),
      weakest_leg_id: customLegs[customLegs.length - 1]?.id ?? null,
      warnings: [],
    };
  }, [customLegs]);

  function togglePick(id: string) {
    setSelectedPickIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  async function saveTicket() {
    if (!selectedCard || !id) return;
    const numericStake = Number(stake);
    if (!Number.isFinite(numericStake) || numericStake < 0) {
      setError("Enter a valid stake amount");
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
      setSelectedCard(null);
      router.push(`/ticket/${ticket.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Ticket could not be saved");
    } finally {
      setSaving(false);
    }
  }

  if (!analysis) {
    return (
      <Screen>
        <BrandHeader title="ANALYSIS EXPIRED" compact />
        <ErrorNotice message="This in-memory analysis is no longer available. Run the slate again; stored recommendations remain protected on the server." />
        <YwpButton label="BACK TO PROTOCOL RUN" onPress={() => router.replace("/(tabs)/slate")} />
      </Screen>
    );
  }

  const officialPass =
    analysis.data_quality_summary.official_pass === true ||
    analysis.ranked_picks.length === 0 ||
    build?.official_pass === true;

  return (
    <Screen sport={analysis.ranked_picks[0]?.sport ?? analysis.stay_away[0]?.sport}>
      <BrandHeader
        title="DECISION BOARD"
        subtitle="FINAL SWEEP • BUILD YOUR OWN"
        compact
        sport={analysis.ranked_picks[0]?.sport ?? analysis.stay_away[0]?.sport}
      />
      <MetalPanel
        tone={
          analysis.data_quality_summary.protocol_status === "DOUBLE_CLEARED"
            ? "success"
            : "danger"
        }
      >
        <View style={styles.summaryTop}>
          <View style={styles.flex}>
            <Text style={type.eyebrow}>PROTOCOL HEALTH</Text>
            <Text style={styles.title}>YWP OS full sweep complete</Text>
          </View>
          <StatusPill value={analysis.data_quality_summary.protocol_status} />
        </View>
        <View style={styles.metrics}>
          <Metric label="Candidates" value={analysis.data_quality_summary.candidate_count} />
          <Metric
            label="Qualified"
            value={analysis.ranked_picks.length}
            accent={colors.success}
          />
          <Metric
            label="Official PASS"
            value={analysis.stay_away.length}
            accent={colors.danger}
          />
          <Metric
            label="Data quality"
            value={`${(analysis.data_quality_summary.average_data_quality * 100).toFixed(0)}%`}
          />
        </View>
        <Text style={type.caption}>
          {analysis.readiness ?? analysis.data_quality_summary.readiness ?? "DEMO"} •
          Model {analysis.model_version} • Analysis {analysis.analysis_id.slice(0, 8)} •
          unknown source labels {analysis.data_quality_summary.unknown_source_labels}
        </Text>
      </MetalPanel>
      {error ? <ErrorNotice message={error} /> : null}

      <SectionTitle
        title="Ranked Plays"
        subtitle="Tap any PLAY or LEAN to build your own ticket. Official cards stay available below."
      />
      {analysis.ranked_picks.length ? (
        analysis.ranked_picks.map((item) => (
          <RecommendationCard
            key={item.id}
            item={item}
            selected={selectedPickIds.includes(item.id)}
            onPress={
              officialPass || !["PLAY", "LEAN"].includes(item.decision)
                ? undefined
                : () => togglePick(item.id)
            }
          />
        ))
      ) : (
        <MetalPanel tone="danger">
          <StatusPill value="SKIP" />
          <Text style={styles.title}>No plays qualified.</Text>
          <Text style={type.body}>
            This is an official PASS—not an incomplete result and not a request to
            add random legs.
          </Text>
        </MetalPanel>
      )}
      {!officialPass && customLegs.length ? (
        <YwpButton
          label={`SAVE CUSTOM ${customLegs.length}-LEG TICKET`}
          onPress={() => customCard && setSelectedCard(customCard)}
        />
      ) : null}
      {!officialPass && analysis.ranked_picks.length ? (
        <Text style={type.caption}>
          {selectedPickIds.length
            ? `${selectedPickIds.length} play${selectedPickIds.length === 1 ? "" : "s"} selected. You are not stuck with the printed cards.`
            : "Tap plays to assemble a custom ticket, or open an official card below."}
        </Text>
      ) : null}

      <SectionTitle
        title="Official Cards"
        subtitle="Max Bet, Elite 2, Core, Cash Builder, special cards, and correct ABC logic."
      />
      {loading ? <LoadingState label="Eliminating weakest legs and duplicate theses…" /> : null}
      {!loading && !build ? (
        <YwpButton label="RE-RUN TICKET BUILDER" onPress={() => void runBuilder()} />
      ) : null}
      {officialPass ? (
        <MetalPanel tone="danger">
          <StatusPill value="PASS" />
          <Text style={styles.title}>Official PASS. No tickets.</Text>
          <Text style={type.body}>
            Open and Save stay disabled. PASS is the product output—not an empty
            board waiting for filler legs.
          </Text>
        </MetalPanel>
      ) : (
        orderedCards.map((card) => (
          <TicketCardView
            key={card.key}
            card={card}
            onPress={card.legs.length ? () => setSelectedCard(card) : undefined}
          />
        ))
      )}

      {build?.quarantined.length ? (
        <>
          <SectionTitle title="Quarantine" subtitle="Exposure or Miss-by-1 controls removed these legs." />
          <MetalPanel tone="danger">
            {build.quarantined.map((item) => (
              <Text key={`${item.recommendation_id}-${item.reason}`} style={styles.quarantine}>
                ⛔ {item.reason}
              </Text>
            ))}
          </MetalPanel>
        </>
      ) : null}

      <SectionTitle
        title="Stay Away"
        subtitle="Failed gates stay visible so a PASS cannot quietly become a pick."
      />
      {analysis.stay_away.map((item) => (
        <RecommendationCard key={item.id} item={item} />
      ))}

      <Modal
        visible={Boolean(selectedCard)}
        transparent
        animationType="slide"
        onRequestClose={() => setSelectedCard(null)}
      >
        <Pressable style={styles.backdrop} onPress={() => setSelectedCard(null)}>
          <Pressable style={styles.modal} onPress={(event) => event.stopPropagation()}>
            <Text style={type.eyebrow}>SAVE DRAFT TICKET</Text>
            <Text style={styles.modalTitle}>{selectedCard?.label}</Text>
            <Text style={type.caption}>
              Saving is not placement. Lock Check is still mandatory immediately
              before any wager.
            </Text>
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
              disabled={officialPass || !selectedCard?.legs.length}
            />
            <YwpButton
              label="CREATE SHARE GRAPHIC"
              variant="outline"
              onPress={() => {
                if (!selectedCard || !id) return;
                setSelectedCard(null);
                router.push({
                  pathname: "/share-card",
                  params: { analysisId: id, cardKey: selectedCard.key },
                });
              }}
            />
            <YwpButton label="CANCEL" variant="danger" onPress={() => setSelectedCard(null)} />
          </Pressable>
        </Pressable>
      </Modal>
    </Screen>
  );
}

const styles = StyleSheet.create({
  summaryTop: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1, gap: spacing.xs },
  title: { color: colors.white, fontSize: 20, fontWeight: "900" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  quarantine: { color: colors.danger, fontSize: 13, lineHeight: 19 },
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
