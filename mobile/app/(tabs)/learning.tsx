import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { EngineStage } from "@/components/EngineStage";
import { ErrorNotice } from "@/components/ErrorNotice";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Metric } from "@/components/Metric";
import { MotionReveal } from "@/components/MotionReveal";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing, type } from "@/theme";
import type {
  HiveProgressReport,
  LearningPulse,
  MissByOneReport,
  OpsHealCycle,
  OpsHealEvidence,
  OpsHealProposal,
  Performance,
  ProtocolDefinition,
  SettleDayResponse,
} from "@/types";

interface Patterns {
  root_cause_tags: Array<{ tag: string; count: number }>;
  duplicate_thesis_losses: Array<{
    thesis_key: string;
    loss_count: number;
    recommendation_ids: string[];
  }>;
  recent_learning_events: Array<{
    event_type: string;
    sport: string | null;
    market_type: string | null;
    analysis: Record<string, unknown>;
    created_at: string;
  }>;
}

export default function LearningScreen() {
  const { user, request } = useAuth();
  const isAdmin = (user?.role ?? "").toLowerCase() === "admin";
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [miss, setMiss] = useState<MissByOneReport | null>(null);
  const [patterns, setPatterns] = useState<Patterns | null>(null);
  const [protocol, setProtocol] = useState<ProtocolDefinition | null>(null);
  const [pulse, setPulse] = useState<LearningPulse | null>(null);
  const [hiveReports, setHiveReports] = useState<HiveProgressReport[]>([]);
  const [opsHeal, setOpsHeal] = useState<OpsHealCycle | null>(null);
  const [proposals, setProposals] = useState<OpsHealProposal[]>([]);
  const [evidence, setEvidence] = useState<OpsHealEvidence | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncNote, setSyncNote] = useState<string | null>(null);

  const load = useCallback(
    async (refresh = false) => {
      refresh ? setRefreshing(true) : setLoading(true);
      setError(null);
      try {
        // Pull finals + map Hive outcomes so optimum-accuracy can move.
        try {
          const settle = await request<SettleDayResponse>("/sports/settle-day", {
            method: "POST",
            body: "{}",
          });
          const mapped = settle.hive_outcomes_mapped ?? 0;
          const graded = (settle.graded ?? 0) + (settle.board_graded ?? 0);
          let healNote = "";
          try {
            const heal = await request<OpsHealCycle>("/ops-heal/run", {
              method: "POST",
              body: "{}",
            });
            setOpsHeal(heal);
            if (isAdmin && heal?.evidence) setEvidence(heal.evidence);
            if (heal?.proposals?.length) {
              setProposals(heal.proposals);
            }
            if (heal?.explanation) {
              const pending = heal.proposals_pending ?? heal.proposals?.length ?? 0;
              healNote =
                pending > 0
                  ? ` · Ops Heal ${heal.status ?? "ran"} · ${pending} change brief${pending === 1 ? "" : "s"}`
                  : ` · Ops Heal ${heal.status ?? "ran"}`;
            }
          } catch {
            // Ops Heal is best-effort; Learning still loads Hive pulse.
          }
          if (mapped || graded) {
            setSyncNote(
              `Hive sync: ${graded} graded · ${mapped} outcome${mapped === 1 ? "" : "s"} mapped${healNote}`,
            );
          } else if (settle.pending) {
            setSyncNote(`${settle.pending} still waiting on finals${healNote}`);
          } else if (healNote) {
            setSyncNote(`Ops Heal ran${healNote}`);
          } else {
            setSyncNote(null);
          }
        } catch {
          // Learning screen still loads pulse/performance if settle is cold.
        }
        const [
          nextPerformance,
          nextMiss,
          nextPatterns,
          nextProtocol,
          nextPulse,
          nextHive,
          nextHeal,
          nextProposals,
          nextEvidence,
        ] = await Promise.all([
            request<Performance>("/learning/performance"),
            request<MissByOneReport>("/learning/miss-by-one"),
            request<Patterns>("/learning/patterns"),
            request<ProtocolDefinition>("/protocol/current"),
            request<LearningPulse>("/learning/pulse"),
            request<{ reports: HiveProgressReport[] }>("/hive/progress-reports?limit=12"),
            request<OpsHealCycle>("/ops-heal/status").catch(() => null),
            request<{ proposals: OpsHealProposal[] }>("/ops-heal/proposals?status=pending&limit=20").catch(
              () => ({ proposals: [] as OpsHealProposal[] }),
            ),
            isAdmin
              ? request<OpsHealEvidence>("/ops-heal/evidence").catch(() => null)
              : Promise.resolve(null),
          ]);
        setPerformance(nextPerformance);
        setMiss(nextMiss);
        setPatterns(nextPatterns);
        setProtocol(nextProtocol);
        setPulse(nextPulse);
        setHiveReports(nextHive.reports ?? []);
        if (nextHeal) setOpsHeal(nextHeal);
        setProposals(nextProposals.proposals ?? []);
        if (isAdmin) {
          if (nextEvidence) setEvidence(nextEvidence);
          else if (nextHeal?.evidence) setEvidence(nextHeal.evidence);
        } else {
          setEvidence(null);
        }
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Learning data failed to load");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [isAdmin, request],
  );
    async (proposalId: string, action: "implemented" | "dismissed") => {
      try {
        await request(`/ops-heal/proposals/${proposalId}/review`, {
          method: "POST",
          body: JSON.stringify({ action }),
        });
        setProposals((prev) => prev.filter((row) => row.id !== proposalId));
        setSyncNote(
          action === "implemented"
            ? "Marked improvement as implemented"
            : "Dismissed improvement brief",
        );
      } catch (reason) {
        setError(
          reason instanceof Error ? reason.message : "Could not update improvement brief",
        );
      }
    },
    [request],
  );

  if (loading) {
    return (
      <Screen>
        <BrandHeader title="ADAPTIVE LEARNING" compact />
        <LoadingState label="Separating process from outcome…" />
      </Screen>
    );
  }

  return (
    <Screen refreshing={refreshing} onRefresh={() => void load(true)}>
      <BrandHeader title="ADAPTIVE LEARNING" subtitle="EVERY GRADE TRAINS THE ENGINE" compact />
      <MotionReveal fromY={20}>
        <EngineStage
          size={168}
          tone="idle"
          intensity="standard"
          label="Hive"
          calloutsActive
          callouts={[
            { id: "grades", label: `${pulse?.graded_results ?? 0} GRADES`, side: "left", top: 40 },
            { id: "shifts", label: `${pulse?.micro_updates ?? 0} SHIFTS`, side: "right", top: 56 },
            { id: "runs", label: `${pulse?.protocol_runs ?? 0} RUNS`, side: "left", top: 110 },
            { id: "train", label: "TRAINING", side: "right", top: 126 },
          ]}
        />
      </MotionReveal>
      {error ? <ErrorNotice message={error} /> : null}
      {syncNote ? (
        <Text style={type.caption}>{syncNote}</Text>
      ) : null}
      <MetalPanel tone="gold">
        <View style={styles.row}>
          <View style={styles.flex}>
            <Text style={type.eyebrow}>SELF-LEARNING PROTOCOL</Text>
            <Text style={styles.title}>Every use makes it smarter.</Text>
          </View>
          <StatusPill value="TRAINING" />
        </View>
        <Text style={type.body}>
          {pulse?.headline ??
            "Opening Learning syncs finals (MLB + ESPN sports), maps Hive outcomes, and unlocks blend once enough settled samples land. Pull to refresh to sync again."}
        </Text>
        {pulse?.latest_lesson ? (
          <Text style={type.caption}>Latest lesson: {pulse.latest_lesson}</Text>
        ) : null}
        <View style={styles.metrics}>
          <Metric label="Protocol runs" value={pulse?.protocol_runs ?? 0} />
          <Metric label="Grades" value={pulse?.graded_results ?? 0} accent={colors.gold} />
          <Metric
            label="Live shifts"
            value={pulse?.micro_updates ?? 0}
            accent={colors.success}
          />
        </View>
      </MetalPanel>

      <SectionTitle
        title="Hive Progress Reports"
        subtitle="Pick calibration from settled WIN/LOSS — separate from product self-heal."
      />
      <MetalPanel tone={hiveReports.length ? "success" : "default"}>
        {hiveReports.length ? (
          hiveReports.slice(0, 8).map((report) => {
            const maturity = (report.maturity ?? {}) as Record<string, unknown>;
            const pct = Number(maturity.optimum_accuracy_pct ?? 0);
            const status = String(maturity.status ?? "collecting");
            return (
              <View key={report.id} style={styles.dataRow}>
                <View style={styles.flex}>
                  <Text style={styles.dataName}>
                    {report.trigger ?? "report"} • {report.created_at?.slice(0, 16) ?? "—"}
                  </Text>
                  <Text style={type.caption}>
                    {report.notes ?? `${report.sample_count} eligible samples`}
                  </Text>
                </View>
                <Text style={styles.dataValue}>
                  {pct.toFixed(1)}% • {status}
                </Text>
              </View>
            );
          })
        ) : (
          <Text style={type.body}>
            No automatic Hive reports yet. Run boards, place/lock tickets, then Sync Scores —
            each graded outcome writes a progress snapshot and strengthens tomorrow’s blends.
          </Text>
        )}
      </MetalPanel>

      <SectionTitle
        title="Ops Heal"
        subtitle="Product health bot — Day Forge, Decision Board, settlement stalls. Allowlisted fixes only."
      />
      <MetalPanel
        tone={
          opsHeal?.status === "healthy"
            ? "success"
            : opsHeal?.status === "critical"
              ? "danger"
              : "default"
        }
      >
        <View style={styles.row}>
          <View style={styles.flex}>
            <Text style={type.eyebrow}>PRODUCT SELF-HEAL</Text>
            <Text style={styles.title}>
              {opsHeal?.status === "idle"
                ? "Standing by"
                : opsHeal?.status
                  ? opsHeal.status.replaceAll("_", " ")
                  : "Not run yet"}
            </Text>
          </View>
          <StatusPill
            value={(opsHeal?.status ?? "IDLE").toUpperCase()}
          />
        </View>
        <Text style={type.body}>
          {opsHeal?.explanation ??
            "Ops Heal collects product health evidence, applies allowlisted runtime fixes, and drafts change briefs for you to implement when you check in."}
        </Text>
        {(opsHeal?.contracts ?? []).length ? (
          <View style={{ marginTop: spacing.sm }}>
            {(opsHeal?.contracts ?? []).map((contract) => (
              <View key={contract.contract_id} style={styles.dataRow}>
                <View style={styles.flex}>
                  <Text style={styles.dataName}>{contract.title}</Text>
                  <Text style={type.caption}>{contract.detail}</Text>
                </View>
                <Text
                  style={[
                    styles.dataValue,
                    { color: contract.ok ? colors.success : colors.danger },
                  ]}
                >
                  {contract.ok ? "OK" : contract.severity.toUpperCase()}
                </Text>
              </View>
            ))}
          </View>
        ) : null}
        {(opsHeal?.applied_remediations ?? []).length ? (
          <Text style={[type.caption, { marginTop: spacing.sm }]}>
            Applied:{" "}
            {(opsHeal?.applied_remediations ?? [])
              .map((r) => r.remediation_id)
              .join(", ")}
          </Text>
        ) : null}
      </MetalPanel>

      {isAdmin ? (
        <>
          <SectionTitle
            title="Process Evidence"
            subtitle="Admin only — every app movement across slate, Day Forge, board, tickets, settle, Hive, Learning."
          />
          <MetalPanel tone={(evidence?.summary?.total_movements ?? 0) > 0 ? "success" : "default"}>
            <View style={styles.metrics}>
              <Metric
                label="Processes active"
                value={`${evidence?.summary?.processes_active ?? 0}/${evidence?.summary?.processes_tracked ?? 0}`}
              />
              <Metric
                label="Movements"
                value={evidence?.summary?.total_movements ?? 0}
                accent={colors.gold}
              />
              <Metric
                label="Errors"
                value={evidence?.summary?.total_errors ?? 0}
                accent={(evidence?.summary?.total_errors ?? 0) > 0 ? colors.danger : colors.success}
              />
            </View>
            {(evidence?.process_coverage ?? []).filter((row) => row.active).length ? (
              <View style={{ marginTop: spacing.sm }}>
                {(evidence?.process_coverage ?? [])
                  .filter((row) => row.active)
                  .slice(0, 12)
                  .map((row) => (
                    <View key={row.process} style={styles.dataRow}>
                      <Text style={styles.dataName}>{row.process.replaceAll("_", " ")}</Text>
                      <Text
                        style={[
                          styles.dataValue,
                          { color: row.errors ? colors.danger : colors.success },
                        ]}
                      >
                        {row.movements} move{row.movements === 1 ? "" : "s"}
                        {row.errors ? ` · ${row.errors} err` : ""}
                      </Text>
                    </View>
                  ))}
              </View>
            ) : (
              <Text style={[type.body, { marginTop: spacing.sm }]}>
                No process movements in the current window yet. Use the app — every API/process path
                feeds this evidence pack for Ops Heal.
              </Text>
            )}
          </MetalPanel>
        </>
      ) : null}

      <SectionTitle
        title="Improvement Inbox"
        subtitle="Ops Heal collects evidence and drafts change briefs. You implement them when you check in."
      />
      <MetalPanel tone={proposals.length ? "gold" : "default"}>
        {proposals.length ? (
          proposals.slice(0, 8).map((proposal) => (
            <View key={proposal.id} style={{ marginBottom: spacing.md }}>
              <View style={styles.row}>
                <View style={styles.flex}>
                  <Text style={type.eyebrow}>
                    {(proposal.area ?? "product").replaceAll("_", " ").toUpperCase()}
                    {proposal.priority ? ` · ${proposal.priority.toUpperCase()}` : ""}
                    {proposal.sightings && proposal.sightings > 1
                      ? ` · seen ${proposal.sightings}x`
                      : ""}
                  </Text>
                  <Text style={styles.title}>{proposal.title}</Text>
                </View>
                <StatusPill value={(proposal.status ?? "pending").toUpperCase()} />
              </View>
              {proposal.summary ? <Text style={type.body}>{proposal.summary}</Text> : null}
              {proposal.recommended_change ? (
                <Text style={[type.caption, { marginTop: spacing.xs }]}>
                  Change: {proposal.recommended_change}
                </Text>
              ) : null}
              <View style={[styles.row, { marginTop: spacing.sm, gap: spacing.sm }]}>
                <YwpButton
                  label="MARK IMPLEMENTED"
                  onPress={() => void reviewProposal(proposal.id, "implemented")}
                />
                <YwpButton
                  label="DISMISS"
                  variant="outline"
                  onPress={() => void reviewProposal(proposal.id, "dismissed")}
                />
              </View>
            </View>
          ))
        ) : (
          <Text style={type.body}>
            No pending change briefs yet. Open Learning / Sync Scores and Ops Heal will draft
            improvements from Day Forge freezes, board errors, and settlement gaps — ready when you
            check in.
          </Text>
        )}
      </MetalPanel>

      {(pulse?.active_shifts ?? []).length ? (
        <>
          <SectionTitle
            title="Live Weight Shifts"
            subtitle="Micro-learning already moved these features. Large jumps still wait for approval."
          />
          <MetalPanel>
            {pulse?.active_shifts.slice(0, 8).map((shift) => (
              <View
                key={`${shift.sport}-${shift.market_type}-${shift.feature_name}-${shift.version}`}
                style={styles.dataRow}
              >
                <Text style={styles.dataName}>
                  {shift.sport} {shift.market_type.replaceAll("_", " ")} • {shift.feature_name.replaceAll("_", " ")}
                </Text>
                <Text style={styles.dataValue}>
                  {(shift.weight * 100).toFixed(1)} • v{shift.version} • n={shift.sample_size}
                </Text>
              </View>
            ))}
          </MetalPanel>
        </>
      ) : null}

      <SectionTitle
        title="Performance"
        subtitle="Leg hit rate ≠ ticket hit rate. Packaging is tracked separately."
      />
      <MetalPanel>
        <Text style={type.eyebrow}>LEG / BOARD PICKS</Text>
        <View style={styles.metrics}>
          <Metric label="Legs settled" value={performance?.leg_settled ?? performance?.settled ?? 0} />
          <Metric
            label="Leg wins"
            value={performance?.leg_wins ?? performance?.wins ?? 0}
            accent={colors.success}
          />
          <Metric
            label="Leg losses"
            value={performance?.leg_losses ?? performance?.losses ?? 0}
            accent={colors.danger}
          />
          <Metric
            label="Leg hit rate"
            value={
              (performance?.leg_win_rate ?? performance?.win_rate) == null
                ? "—"
                : `${(((performance?.leg_win_rate ?? performance?.win_rate) as number) * 100).toFixed(1)}%`
            }
          />
        </View>
        <Text style={[type.eyebrow, { marginTop: spacing.md }]}>FULL TICKETS</Text>
        <View style={styles.metrics}>
          <Metric label="Tickets settled" value={performance?.ticket_settled ?? 0} />
          <Metric label="Ticket wins" value={performance?.ticket_wins ?? 0} accent={colors.success} />
          <Metric label="Ticket losses" value={performance?.ticket_losses ?? 0} accent={colors.danger} />
          <Metric
            label="Ticket hit rate"
            value={
              performance?.ticket_win_rate == null
                ? "—"
                : `${(performance.ticket_win_rate * 100).toFixed(1)}%`
            }
          />
          <Metric
            label="Packaging gap"
            value={
              performance?.packaging_gap == null
                ? "—"
                : `${performance.packaging_gap >= 0 ? "+" : ""}${(performance.packaging_gap * 100).toFixed(1)}%`
            }
            accent={
              performance?.packaging_gap == null
                ? undefined
                : performance.packaging_gap >= 0.08
                  ? colors.danger
                  : colors.success
            }
          />
          <Metric
            label="Locked-leg rate"
            value={
              performance?.locked_leg_win_rate == null
                ? "—"
                : `${(performance.locked_leg_win_rate * 100).toFixed(1)}%`
            }
          />
        </View>
        {performance?.packaging_note ? (
          <Text style={[type.caption, { marginTop: spacing.sm }]}>{performance.packaging_note}</Text>
        ) : null}
        <View style={[styles.metrics, { marginTop: spacing.md }]}>
          <Metric
            label="P/L"
            value={`$${Number(performance?.profit_loss ?? 0).toFixed(2)}`}
            accent={Number(performance?.profit_loss ?? 0) >= 0 ? colors.success : colors.danger}
          />
          <Metric
            label="ROI"
            value={
              performance?.roi === null || performance?.roi === undefined
                ? "—"
                : `${(performance.roi * 100).toFixed(1)}%`
            }
          />
        </View>
        {(performance?.by_ticket_type ?? []).length ? (
          <>
            <Text style={[type.eyebrow, { marginTop: spacing.md }]}>BY TICKET TYPE</Text>
            {(performance?.by_ticket_type ?? []).map((row, index) => (
              <View key={`${String(row.ticket_type)}-${index}`} style={styles.dataRow}>
                <Text style={styles.dataName}>
                  {String(row.ticket_type ?? "unknown").replaceAll("_", " ")}
                </Text>
                <Text style={styles.dataValue}>
                  {row.win_rate == null ? "—" : `${(Number(row.win_rate) * 100).toFixed(0)}%`} •{" "}
                  {String(row.wins ?? 0)}/{String(row.settled ?? 0)}
                </Text>
              </View>
            ))}
          </>
        ) : null}
      </MetalPanel>

      <SectionTitle
        title="Miss-by-1 Lab"
        subtitle="Slips are counted separately from unique failed theses."
      />
      <MetalPanel tone={miss?.near_miss_results ? "danger" : "success"}>
        <View style={styles.metrics}>
          <Metric label="Near misses" value={miss?.near_miss_results ?? 0} accent={colors.warning} />
          <Metric label="Ticket killers" value={miss?.tickets_killed_by_near_miss ?? 0} accent={colors.danger} />
          <Metric label="Final losing leg" value={miss?.last_leg_near_misses ?? 0} accent={colors.danger} />
        </View>
        {(miss?.by_market ?? []).slice(0, 8).map((row, index) => (
          <View key={`${String(row.market_type)}-${index}`} style={styles.dataRow}>
            <Text style={styles.dataName}>{String(row.market_type ?? "unknown").replaceAll("_", " ")}</Text>
            <Text style={styles.dataValue}>{String(row.near_misses ?? 0)} near misses</Text>
          </View>
        ))}
        {!miss?.near_miss_results ? (
          <Text style={type.body}>No near-miss result has been graded yet.</Text>
        ) : null}
      </MetalPanel>

      <SectionTitle title="Recurring Root Causes" subtitle="Patterns are evidence, not automatic commands." />
      <MetalPanel>
        {patterns?.root_cause_tags.length ? (
          patterns.root_cause_tags.map((item) => (
            <View key={item.tag} style={styles.dataRow}>
              <Text style={styles.dataName}>{item.tag.replaceAll("_", " ")}</Text>
              <Text style={styles.count}>{item.count}</Text>
            </View>
          ))
        ) : (
          <Text style={type.body}>No recurring failure mode has enough logged evidence.</Text>
        )}
      </MetalPanel>

      <SectionTitle title="Confidence Calibration" subtitle="High ratings must earn high observed hit rates." />
      <MetalPanel>
        {performance?.confidence_calibration.length ? (
          performance.confidence_calibration.map((item) => (
            <View key={String(item.confidence_band)} style={styles.dataRow}>
              <Text style={styles.dataName}>Band {String(item.confidence_band)}</Text>
              <Text style={styles.dataValue}>
                {Number(item.observed_win_rate ?? 0) * 100}% observed • {String(item.settled)} settled
              </Text>
            </View>
          ))
        ) : (
          <Text style={type.body}>Calibration appears after graded results accumulate.</Text>
        )}
      </MetalPanel>

      <SectionTitle title="Guardrails" subtitle="These controls are part of the active protocol." />
      <MetalPanel tone="success">
        {(protocol?.adaptive_learning.guardrails ?? []).map((guardrail) => (
          <Text key={guardrail} style={styles.guardrail}>✓ {guardrail}</Text>
        ))}
        <Text style={styles.guardrail}>
          ✓ Every graded result applies a tiny bounded weight shift immediately
        </Text>
      </MetalPanel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1, gap: spacing.xs },
  title: { color: colors.white, fontSize: 22, fontWeight: "900" },
  metrics: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  dataRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.sm,
  },
  dataName: { flex: 1, color: colors.white, fontSize: 13, fontWeight: "800", textTransform: "uppercase" },
  dataValue: { color: colors.muted, fontSize: 12, textAlign: "right" },
  count: { color: colors.gold, fontSize: 20, fontWeight: "900" },
  guardrail: { color: colors.success, fontSize: 13, lineHeight: 20 },
});
