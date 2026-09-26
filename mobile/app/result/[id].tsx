import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { colors, radius, spacing, type } from "@/theme";
import type { Recommendation, ResultRecord } from "@/types";

const outcomes = ["WIN", "LOSS", "PUSH", "VOID"];
const processGrades = ["A", "B", "C", "D", "F"];
const varianceGrades = ["LOW", "MEDIUM", "HIGH"];
const errorCategories = [
  "UNKNOWN",
  "VARIANCE",
  "BAD_DATA",
  "BAD_WEIGHTING",
  "BAD_SCRIPT",
  "BAD_TIMING",
  "BAD_PRICE",
  "ROLE_WORKLOAD",
  "INJURY_AVAILABILITY",
  "CORRELATION_EXPOSURE",
  "LINE_ESCALATION",
];
const triggerResults = ["HIT", "MISS", "NOT_TRIGGERED", "NOT_APPLICABLE"];
const quickResults = ["HIT", "MISS", "NOT_APPLICABLE"];
const cashoutActions = [
  "NOT_APPLICABLE",
  "NOT_OFFERED",
  "HOLD",
  "CASH_OUT",
  "PARTIAL_HEDGE",
];

function csv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function ChoiceRow({
  values,
  value,
  onChange,
}: {
  values: string[];
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <View style={styles.choices}>
      {values.map((item) => (
        <Pressable
          key={item}
          accessibilityRole="button"
          accessibilityState={{ selected: value === item }}
          onPress={() => onChange(item)}
          style={[styles.choice, value === item && styles.choiceActive]}
        >
          <Text style={[styles.choiceText, value === item && styles.choiceTextActive]}>
            {item.replaceAll("_", " ")}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

function optional(value: string): string | undefined {
  return value.trim() ? value.trim() : undefined;
}

export default function ResultGradeScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { request } = useAuth();
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [record, setRecord] = useState<ResultRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState("WIN");
  const [processGrade, setProcessGrade] = useState("A");
  const [varianceGrade, setVarianceGrade] = useState("MEDIUM");
  const [errorCategory, setErrorCategory] = useState("UNKNOWN");
  const [stake, setStake] = useState("0.00");
  const [profitLoss, setProfitLoss] = useState("0.00");
  const [finalScore, setFinalScore] = useState("");
  const [actualValue, setActualValue] = useState("");
  const [betLine, setBetLine] = useState("");
  const [closingLine, setClosingLine] = useState("");
  const [closingOdds, setClosingOdds] = useState("");
  const [killedTicket, setKilledTicket] = useState(false);
  const [lastLosingLeg, setLastLosingLeg] = useState(false);
  const [assumptionsHeld, setAssumptionsHeld] = useState("");
  const [assumptionsFailed, setAssumptionsFailed] = useState("");
  const [unexpectedEvents, setUnexpectedEvents] = useState("");
  const [rootCauses, setRootCauses] = useState("");
  const [lesson, setLesson] = useState("");
  const [quickCashResult, setQuickCashResult] = useState("NOT_APPLICABLE");
  const [chainResult, setChainResult] = useState("NOT_APPLICABLE");
  const [liveTriggerResult, setLiveTriggerResult] = useState("NOT_APPLICABLE");
  const [cashoutAction, setCashoutAction] = useState("NOT_APPLICABLE");
  const [cashoutOffer, setCashoutOffer] = useState("");
  const [cashoutReason, setCashoutReason] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const item = await request<Recommendation>(`/sports/recommendations/${id}`);
      setRecommendation(item);
      setBetLine(item.line ?? "");
      setQuickCashResult("NOT_APPLICABLE");
      setChainResult(item.chain_reaction_key ? "NOT_TRIGGERED" : "NOT_APPLICABLE");
      setLiveTriggerResult(item.live_trigger ? "NOT_TRIGGERED" : "NOT_APPLICABLE");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Recommendation failed to load");
    } finally {
      setLoading(false);
    }
  }, [id, request]);

  useEffect(() => {
    void load();
  }, [load]);

  const processClass = useMemo(() => {
    const goodProcess = ["A", "B"].includes(processGrade);
    const goodOutcome = outcome === "WIN";
    if (goodProcess && goodOutcome) return "GOOD_PROCESS_GOOD_OUTCOME";
    if (goodProcess) return "GOOD_PROCESS_BAD_OUTCOME";
    if (goodOutcome) return "BAD_PROCESS_GOOD_OUTCOME";
    return "BAD_PROCESS_BAD_OUTCOME";
  }, [outcome, processGrade]);

  const cashoutActed = ["HOLD", "CASH_OUT", "PARTIAL_HEDGE"].includes(cashoutAction);

  async function submit() {
    if (!id) return;
    if (!Number.isFinite(Number(stake)) || !Number.isFinite(Number(profitLoss))) {
      setError("Stake and profit/loss must be valid numbers.");
      return;
    }
    if (cashoutActed && (!cashoutOffer.trim() || !cashoutReason.trim())) {
      setError("A recorded live action requires the cash-out offer and decision reason.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const held = csv(assumptionsHeld).map((item) => `HELD: ${item}`);
      const failed = csv(assumptionsFailed).map((item) => `FAILED: ${item}`);
      const next = await request<ResultRecord>("/sports/result", {
        method: "POST",
        body: JSON.stringify({
          recommendation_id: id,
          outcome,
          final_score: optional(finalScore),
          stake,
          profit_loss: profitLoss,
          closing_odds: closingOdds.trim() ? Number(closingOdds) : undefined,
          closing_line: optional(closingLine),
          actual_value: optional(actualValue),
          bet_line: optional(betLine),
          killed_ticket: outcome === "LOSS" && killedTicket,
          last_losing_leg: outcome === "LOSS" && lastLosingLeg,
          process_outcome_class: processClass,
          error_category: errorCategory,
          assumptions_review: [...held, ...failed],
          unexpected_events: csv(unexpectedEvents),
          quick_cash_result: quickCashResult,
          chain_reaction_result: chainResult,
          live_trigger_result: liveTriggerResult,
          cashout_action: cashoutAction,
          cashout_offer: cashoutActed ? cashoutOffer : undefined,
          cashout_reason: optional(cashoutReason),
          cashout_time: cashoutActed ? new Date().toISOString() : undefined,
          process_grade: processGrade,
          variance_grade: varianceGrade,
          root_cause_tags: csv(rootCauses),
          lesson: optional(lesson),
        }),
      });
      setRecord(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Result could not be recorded");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Screen>
        <BrandHeader title="RESULT & PROCESS" compact />
        <LoadingState label="Loading the stored recommendation…" />
      </Screen>
    );
  }

  if (record) {
    return (
      <Screen>
        <BrandHeader title="RESULT RECORDED" subtitle="OUTCOME ≠ PROCESS" compact />
        <MetalPanel tone={record.outcome === "WIN" ? "success" : "gold"}>
          <StatusPill value={record.outcome} />
          <Text style={styles.title}>Learning ledger updated</Text>
          <View style={styles.metrics}>
            <Metric label="Process" value={record.process_grade} />
            <Metric label="Variance" value={record.variance_grade} />
            <Metric label="P/L" value={`$${record.profit_loss}`} />
            <Metric label="Miss" value={record.miss_distance ?? "—"} />
          </View>
          <Text style={type.body}>
            This grade already trained a tiny weight shift. Repeated patterns can still
            open a larger proposal that needs human approval.
          </Text>
        </MetalPanel>
        <YwpButton label="OPEN LEARNING LAB" onPress={() => router.replace("/(tabs)/learning")} />
        <YwpButton label="BACK" variant="outline" onPress={() => router.back()} />
      </Screen>
    );
  }

  if (!recommendation) {
    return (
      <Screen>
        <ErrorNotice message={error ?? "Recommendation not found"} />
        <YwpButton label="BACK" onPress={() => router.back()} />
      </Screen>
    );
  }

  return (
    <Screen>
      <BrandHeader title="RESULT & PROCESS" subtitle="GRADE HONESTLY • TRAIN THE ENGINE" compact />
      {error ? <ErrorNotice message={error} /> : null}
      <MetalPanel tone="gold">
        <Text style={type.eyebrow}>{recommendation.sport} • {recommendation.market_type.replaceAll("_", " ")}</Text>
        <Text style={styles.title}>{recommendation.selection}</Text>
        <Text style={type.body}>{recommendation.event_name}</Text>
        <Text style={type.caption}>Protocol {recommendation.protocol_version} • Input {recommendation.input_hash.slice(0, 12)}</Text>
      </MetalPanel>

      <SectionTitle title="Outcome" subtitle="A win can have bad process; a loss can have good process." />
      <MetalPanel>
        <ChoiceRow values={outcomes} value={outcome} onChange={setOutcome} />
        <FormField label="Stake" value={stake} onChangeText={setStake} keyboardType="decimal-pad" />
        <FormField label="Profit / loss" value={profitLoss} onChangeText={setProfitLoss} keyboardType="decimal-pad" />
        <FormField label="Final score (optional)" value={finalScore} onChangeText={setFinalScore} />
        <FormField label="Actual result value" value={actualValue} onChangeText={setActualValue} keyboardType="decimal-pad" />
        <FormField label="Played line" value={betLine} onChangeText={setBetLine} keyboardType="decimal-pad" />
        <FormField label="Closing line" value={closingLine} onChangeText={setClosingLine} keyboardType="decimal-pad" />
        <FormField label="Closing American odds" value={closingOdds} onChangeText={setClosingOdds} keyboardType="numbers-and-punctuation" />
        {outcome === "LOSS" ? (
          <>
            <View style={styles.switchRow}>
              <Text style={styles.switchText}>This result killed the ticket</Text>
              <Switch value={killedTicket} onValueChange={setKilledTicket} />
            </View>
            <View style={styles.switchRow}>
              <Text style={styles.switchText}>This was the final losing leg</Text>
              <Switch value={lastLosingLeg} onValueChange={setLastLosingLeg} />
            </View>
          </>
        ) : null}
      </MetalPanel>

      <SectionTitle title="Process Grade" subtitle={`Classification: ${processClass.replaceAll("_", " ")}`} />
      <MetalPanel>
        <Text style={styles.label}>PROCESS</Text>
        <ChoiceRow values={processGrades} value={processGrade} onChange={setProcessGrade} />
        <Text style={styles.label}>VARIANCE</Text>
        <ChoiceRow values={varianceGrades} value={varianceGrade} onChange={setVarianceGrade} />
        <Text style={styles.label}>PRIMARY ERROR CATEGORY</Text>
        <ChoiceRow values={errorCategories} value={errorCategory} onChange={setErrorCategory} />
      </MetalPanel>

      <SectionTitle title="Live & Cash-out Audit" subtitle="Treat every offer as a new price; never react to fear or sunk cost." />
      <MetalPanel tone="gold">
        <Text style={styles.label}>CASH-OUT ACTION</Text>
        <ChoiceRow values={cashoutActions} value={cashoutAction} onChange={setCashoutAction} />
        {cashoutActed ? (
          <>
            <FormField label="Cash-out offer" value={cashoutOffer} onChangeText={setCashoutOffer} keyboardType="decimal-pad" />
            <FormField label="Verified reason" value={cashoutReason} onChangeText={setCashoutReason} multiline />
          </>
        ) : null}
        <Text style={styles.label}>LIVE TRIGGER</Text>
        <ChoiceRow values={triggerResults} value={liveTriggerResult} onChange={setLiveTriggerResult} />
        {recommendation.quick_cash ? (
          <>
            <Text style={styles.label}>QUICK CASH</Text>
            <ChoiceRow values={quickResults} value={quickCashResult} onChange={setQuickCashResult} />
          </>
        ) : null}
        {recommendation.chain_reaction_key ? (
          <>
            <Text style={styles.label}>CHAIN REACTION</Text>
            <ChoiceRow values={triggerResults} value={chainResult} onChange={setChainResult} />
          </>
        ) : null}
      </MetalPanel>

      <SectionTitle title="Error Analysis" subtitle="Assumptions, surprises, cause, and lesson remain separate from the score." />
      <MetalPanel>
        <FormField label="Assumptions that held (comma separated)" value={assumptionsHeld} onChangeText={setAssumptionsHeld} multiline />
        <FormField label="Assumptions that failed (comma separated)" value={assumptionsFailed} onChangeText={setAssumptionsFailed} multiline />
        <FormField label="Unexpected events (comma separated)" value={unexpectedEvents} onChangeText={setUnexpectedEvents} multiline />
        <FormField label="Root-cause tags (comma separated)" value={rootCauses} onChangeText={setRootCauses} />
        <FormField label="Lesson" value={lesson} onChangeText={setLesson} multiline />
      </MetalPanel>

      <YwpButton label="RECORD RESULT & PROCESS" onPress={() => void submit()} loading={saving} />
      <Text style={styles.footer}>Result entry is immutable. Review every field before saving.</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: { color: colors.white, fontSize: 21, fontWeight: "900" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  choices: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  choice: {
    minHeight: 44,
    justifyContent: "center",
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundRaised,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  choiceActive: { borderColor: colors.gold, backgroundColor: colors.surfaceGold },
  choiceText: { color: colors.muted, fontSize: 10, fontWeight: "900" },
  choiceTextActive: { color: colors.gold },
  label: { ...type.eyebrow, marginTop: spacing.sm },
  switchRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  switchText: { flex: 1, color: colors.white, fontSize: 13, fontWeight: "800" },
  footer: { ...type.caption, textAlign: "center", padding: spacing.md },
});
