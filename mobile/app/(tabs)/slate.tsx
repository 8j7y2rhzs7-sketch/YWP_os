import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { LoadingState } from "@/components/LoadingState";
import { MetalPanel } from "@/components/MetalPanel";
import { Screen } from "@/components/Screen";
import { SectionTitle } from "@/components/SectionTitle";
import { StatusPill } from "@/components/StatusPill";
import { YwpButton } from "@/components/YwpButton";
import { useAppData } from "@/context/AppDataContext";
import { useAuth } from "@/context/AuthContext";
import { colors, radius, spacing, type } from "@/theme";
import type { AnalyzeResponse, SlateResponse } from "@/types";

const sports = [
  { key: "mlb", label: "MLB", icon: "⚾" },
  { key: "wnba", label: "WNBA", icon: "🏀" },
  { key: "soccer", label: "SOCCER", icon: "⚽" },
  { key: "nfl", label: "NFL", icon: "🏈" },
  { key: "ncaaf", label: "NCAAF", icon: "🏈" },
  { key: "kbo", label: "KBO", icon: "⚾" },
] as const;

function localDate(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export default function SlateScreen() {
  const { user, request } = useAuth();
  const { saveAnalysis } = useAppData();
  const [sport, setSport] = useState<(typeof sports)[number]["key"]>("mlb");
  const [date, setDate] = useState(localDate());
  const [slate, setSlate] = useState<SlateResponse | null>(null);
  const [loadingSlate, setLoadingSlate] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadSlate() {
    setLoadingSlate(true);
    setError(null);
    try {
      const response = await request<SlateResponse>(
        `/sports/slate?sport=${encodeURIComponent(sport)}&date=${encodeURIComponent(date)}`,
      );
      setSlate(response);
    } catch (reason) {
      setSlate(null);
      setError(reason instanceof Error ? reason.message : "Slate failed to load");
    } finally {
      setLoadingSlate(false);
    }
  }

  async function analyze() {
    if (!slate) return;
    setAnalyzing(true);
    setError(null);
    try {
      const response = await request<AnalyzeResponse>("/sports/analyze", {
        method: "POST",
        body: JSON.stringify({
          sport,
          date,
          mode: "pregame",
          user_risk_profile: user?.risk_profile ?? "balanced",
          candidates: slate.candidates,
        }),
      });
      saveAnalysis(response);
      router.push(`/analysis/${response.analysis_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  useEffect(() => {
    void loadSlate();
    // Reload only when the chosen sport changes. Date changes apply after pressing refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sport]);

  return (
    <Screen>
      <BrandHeader title="FULL PROTOCOL RUN" subtitle="AIN • STRICT MODE • ALL ANGLES" compact />
      <MetalPanel tone="gold">
        <Text style={type.eyebrow}>SELECT SPORT</Text>
        <View style={styles.sports}>
          {sports.map((item) => (
            <Pressable
              key={item.key}
              onPress={() => setSport(item.key)}
              style={[styles.sport, sport === item.key && styles.sportActive]}
            >
              <Text style={styles.sportIcon}>{item.icon}</Text>
              <Text
                style={[
                  styles.sportLabel,
                  sport === item.key && styles.sportLabelActive,
                ]}
              >
                {item.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <FormField
          label="Slate date (YYYY-MM-DD)"
          value={date}
          onChangeText={setDate}
          autoCapitalize="none"
          keyboardType="numbers-and-punctuation"
        />
        <YwpButton
          label="REFRESH RAW SLATE"
          variant="outline"
          onPress={() => void loadSlate()}
          loading={loadingSlate}
        />
      </MetalPanel>

      {error ? <ErrorNotice message={error} /> : null}
      {loadingSlate ? <LoadingState label="Verifying schedule and candidates…" /> : null}

      {slate ? (
        <>
          <MetalPanel tone={slate.mode === "demo" ? "danger" : "success"}>
            <View style={styles.noticeHeader}>
              <Text style={styles.noticeTitle}>{slate.mode.toUpperCase()} DATA SOURCE</Text>
              <StatusPill value={slate.mode === "demo" ? "WARNING" : "LOCKED"} />
            </View>
            <Text style={type.body}>{slate.notice}</Text>
          </MetalPanel>

          <SectionTitle
            title={`Raw ${sport.toUpperCase()} Candidate List`}
            subtitle="Raw list appears before YWP scoring, eliminations, and card building."
          />
          {slate.candidates.map((candidate, index) => (
            <MetalPanel key={candidate.candidate_id} style={styles.candidate}>
              <View style={styles.candidateTop}>
                <Text style={styles.number}>{index + 1}</Text>
                <View style={styles.candidateCopy}>
                  <Text style={styles.selection}>{candidate.selection}</Text>
                  <Text style={type.caption}>{candidate.event_name}</Text>
                </View>
                <Text style={styles.odds}>
                  {candidate.american_odds > 0 ? "+" : ""}
                  {candidate.american_odds}
                </Text>
              </View>
              <Text style={styles.market}>
                {candidate.market_type.replaceAll("_", " ")} • MODEL P{" "}
                {(candidate.estimated_probability * 100).toFixed(1)}% • DATA{" "}
                {(candidate.data_quality * 100).toFixed(0)}%
              </Text>
            </MetalPanel>
          ))}
          <YwpButton
            label="RUN AIN + STRICT MODE + MISS-BY-1"
            onPress={() => void analyze()}
            loading={analyzing}
            disabled={!slate.candidates.length}
          />
          <Text style={styles.footer}>
            Schedule • L5/L10 • matchup • script • line • cushion • role • injuries •
            motivation • variance • value • weakest leg • lock path
          </Text>
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  sports: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  sport: {
    flex: 1,
    minWidth: 92,
    alignItems: "center",
    gap: spacing.xs,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.backgroundRaised,
  },
  sportActive: { borderColor: colors.gold, backgroundColor: colors.surfaceGold },
  sportIcon: { fontSize: 26 },
  sportLabel: { color: colors.muted, fontWeight: "900", fontSize: 11 },
  sportLabelActive: { color: colors.gold },
  noticeHeader: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  noticeTitle: { flex: 1, color: colors.white, fontSize: 16, fontWeight: "900" },
  candidate: { padding: spacing.md },
  candidateTop: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  number: {
    width: 30,
    height: 30,
    borderRadius: 15,
    lineHeight: 30,
    textAlign: "center",
    color: colors.background,
    backgroundColor: colors.gold,
    fontWeight: "900",
  },
  candidateCopy: { flex: 1, gap: 2 },
  selection: { color: colors.white, fontSize: 16, fontWeight: "800" },
  odds: { color: colors.gold, fontSize: 16, fontWeight: "900" },
  market: {
    color: colors.success,
    fontSize: 10,
    fontWeight: "800",
    textTransform: "uppercase",
  },
  footer: { ...type.caption, textAlign: "center", padding: spacing.md },
});
