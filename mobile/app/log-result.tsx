import { router } from "expo-router";
import { useMemo, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { MetalPanel } from "@/components/MetalPanel";
import { Screen } from "@/components/Screen";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { colors, radius, spacing, type } from "@/theme";

const outcomes = ["WIN", "LOSS", "PUSH", "VOID"] as const;
const markets = [
  { label: "Strikeouts Over", value: "player_strikeouts_over" },
  { label: "Moneyline", value: "moneyline" },
  { label: "Total Over", value: "total_over" },
  { label: "Total Under", value: "total_under" },
  { label: "Spread / Run Line", value: "spread" },
  { label: "F5 Winner", value: "f5_moneyline" },
] as const;

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function LogExternalResultScreen() {
  const { request } = useAuth();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [eventName, setEventName] = useState("");
  const [selection, setSelection] = useState("");
  const [marketType, setMarketType] = useState<string>("player_strikeouts_over");
  const [line, setLine] = useState("");
  const [odds, setOdds] = useState("");
  const [outcome, setOutcome] = useState<(typeof outcomes)[number]>("WIN");
  const [actualValue, setActualValue] = useState("");
  const [finalScore, setFinalScore] = useState("");
  const [playerKey, setPlayerKey] = useState("");
  const [lesson, setLesson] = useState(
    "Logged from sportsbook — never locked in YWP OS.",
  );
  const [killedTicket, setKilledTicket] = useState(false);

  const canSave = useMemo(() => {
    return Boolean(eventName.trim() && selection.trim() && odds.trim());
  }, [eventName, selection, odds]);

  async function save() {
    if (!canSave) return;
    setSaving(true);
    setError(null);
    try {
      const oddsInt = Number.parseInt(odds.trim(), 10);
      if (Number.isNaN(oddsInt)) {
        throw new Error("Odds must be an American number like -140 or +110");
      }
      await request("/sports/log-external", {
        method: "POST",
        body: JSON.stringify({
          sport: "mlb",
          league: "MLB",
          slate_date: todayIso(),
          event_name: eventName.trim(),
          market_type: marketType,
          market_period: marketType.startsWith("f5") ? "first_5" : "full_game",
          selection: selection.trim(),
          line: line.trim() ? line.trim() : null,
          american_odds: oddsInt,
          outcome,
          actual_value: actualValue.trim() ? actualValue.trim() : null,
          final_score: finalScore.trim() || null,
          player_key: playerKey.trim() || null,
          killed_ticket: killedTicket,
          process_grade: "C",
          variance_grade: "MEDIUM",
          lesson: lesson.trim() || null,
          root_cause_tags: ["EXTERNAL_BOOK_LOG"],
        }),
      });
      Alert.alert("Logged", "Pick is in WIN/LOSS memory now.", [
        { text: "OK", onPress: () => router.back() },
      ]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not log result");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Screen>
      <BrandHeader
        title="Log Book Result"
        subtitle="For picks you bet on the sportsbook but never locked here — especially strikeouts."
      />
      {error ? <ErrorNotice message={error} /> : null}

      <MetalPanel>
        <Text style={styles.hint}>
          Use this for sportsbook legs that never appeared on today's board
          (strikeouts, F5, book-only parlays).
        </Text>
        <FormField label="EVENT" value={eventName} onChangeText={setEventName} placeholder="Cardinals @ Dodgers" />
        <FormField label="SELECTION" value={selection} onChangeText={setSelection} placeholder="Michael Wacha Over 4.5 Strikeouts" />
        <Text style={styles.label}>MARKET</Text>
        <View style={styles.choices}>
          {markets.map((item) => (
            <Pressable
              key={item.value}
              onPress={() => setMarketType(item.value)}
              style={[styles.choice, marketType === item.value && styles.choiceActive]}
            >
              <Text style={[styles.choiceText, marketType === item.value && styles.choiceTextActive]}>
                {item.label}
              </Text>
            </Pressable>
          ))}
        </View>
        <FormField label="LINE" value={line} onChangeText={setLine} placeholder="4.5" keyboardType="decimal-pad" />
        <FormField label="AMERICAN ODDS" value={odds} onChangeText={setOdds} placeholder="-140" keyboardType="numbers-and-punctuation" />
        <Text style={styles.label}>OUTCOME</Text>
        <View style={styles.choices}>
          {outcomes.map((item) => (
            <Pressable
              key={item}
              onPress={() => setOutcome(item)}
              style={[styles.choice, outcome === item && styles.choiceActive]}
            >
              <Text style={[styles.choiceText, outcome === item && styles.choiceTextActive]}>
                {item}
              </Text>
            </Pressable>
          ))}
        </View>
        <FormField label="ACTUAL VALUE" value={actualValue} onChangeText={setActualValue} placeholder="7" keyboardType="decimal-pad" />
        <FormField label="FINAL / NOTE" value={finalScore} onChangeText={setFinalScore} placeholder="Wacha 7 Ks" />
        <FormField label="PLAYER KEY (optional)" value={playerKey} onChangeText={setPlayerKey} placeholder="michael_wacha" />
        <FormField label="LESSON" value={lesson} onChangeText={setLesson} />
        <Pressable
          onPress={() => setKilledTicket((value) => !value)}
          style={[styles.toggle, killedTicket && styles.toggleOn]}
        >
          <Text style={styles.toggleText}>
            {killedTicket ? "Marked as ticket killer" : "Did this leg kill a parlay?"}
          </Text>
        </Pressable>
      </MetalPanel>

      <YwpButton label="SAVE TO MEMORY" onPress={() => void save()} loading={saving} disabled={!canSave} />
      <Text style={[type.caption, styles.footer]}>
        Does not create a vault ticket. Only grades learning memory.
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hint: { ...type.body, color: colors.muted, marginBottom: spacing.sm },
  label: {
    color: colors.gold,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  choices: { flexDirection: "row", flexWrap: "wrap", gap: spacing.xs },
  choice: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  choiceActive: { borderColor: colors.gold, backgroundColor: colors.goldMute },
  choiceText: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  choiceTextActive: { color: colors.white },
  toggle: {
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.sm,
  },
  toggleOn: { borderColor: colors.danger, backgroundColor: "rgba(180,40,40,0.15)" },
  toggleText: { color: colors.white, fontWeight: "700" },
  footer: { textAlign: "center", marginTop: spacing.sm },
});
