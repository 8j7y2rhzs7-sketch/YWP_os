import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
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
import { useAuth } from "@/context/AuthContext";
import { colors, radius, spacing, type } from "@/theme";
import type {
  Bankroll,
  ProtocolDefinition,
  RiskProfile,
  User,
} from "@/types";

const profiles: RiskProfile[] = ["conservative", "balanced", "aggressive"];

export default function SettingsScreen() {
  const { user, request, reloadUser, logout } = useAuth();
  const [bankroll, setBankroll] = useState<Bankroll | null>(null);
  const [protocol, setProtocol] = useState<ProtocolDefinition | null>(null);
  const [risk, setRisk] = useState<RiskProfile>(user?.risk_profile ?? "balanced");
  const [maxStake, setMaxStake] = useState("2.0");
  const [dailyExposure, setDailyExposure] = useState("10.0");
  const [thesisExposure, setThesisExposure] = useState("3.0");
  const [lossPause, setLossPause] = useState("3");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextBankroll, nextProtocol] = await Promise.all([
        request<Bankroll>("/bankroll"),
        request<ProtocolDefinition>("/protocol/current"),
      ]);
      setBankroll(nextBankroll);
      setProtocol(nextProtocol);
      setMaxStake((Number(nextBankroll.max_stake_pct) * 100).toFixed(1));
      setDailyExposure((Number(nextBankroll.max_daily_exposure_pct) * 100).toFixed(1));
      setThesisExposure((Number(nextBankroll.max_thesis_exposure_pct) * 100).toFixed(1));
      setLossPause(String(nextBankroll.loss_pause_threshold));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Controls failed to load");
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await Promise.all([
        request<User>("/users/me", {
          method: "PATCH",
          body: JSON.stringify({ risk_profile: risk }),
        }),
        request<Bankroll>("/bankroll", {
          method: "PATCH",
          body: JSON.stringify({
            max_stake_pct: Number(maxStake) / 100,
            max_daily_exposure_pct: Number(dailyExposure) / 100,
            max_thesis_exposure_pct: Number(thesisExposure) / 100,
            loss_pause_threshold: Number(lossPause),
          }),
        }),
      ]);
      await reloadUser();
      await load();
      setSaved(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Controls could not be saved");
    } finally {
      setSaving(false);
    }
  }

  async function signOut() {
    await logout();
    router.replace("/(auth)/login");
  }

  if (loading) {
    return (
      <Screen>
        <LoadingState label="Loading bankroll and protocol controls…" />
      </Screen>
    );
  }

  return (
    <Screen>
      <BrandHeader title="SYSTEM CONTROLS" subtitle="BANKROLL • PROTOCOL • ACCOUNT" compact />
      {error ? <ErrorNotice message={error} /> : null}
      {saved ? (
        <MetalPanel tone="success">
          <StatusPill value="LOCKED" />
          <Text style={styles.saved}>Controls saved and audit-logged.</Text>
        </MetalPanel>
      ) : null}

      <SectionTitle title="Account" />
      <MetalPanel>
        <Text style={styles.title}>{user?.name}</Text>
        <Text style={type.body}>{user?.email}</Text>
        <Text style={type.caption}>Timezone {user?.timezone} • Role {user?.role}</Text>
      </MetalPanel>

      <SectionTitle title="Risk Profile" subtitle="This changes stake sizing, not the official daily card." />
      <MetalPanel tone="gold">
        <View style={styles.profileRow}>
          {profiles.map((profile) => (
            <Pressable
              key={profile}
              onPress={() => setRisk(profile)}
              style={[styles.profile, risk === profile && styles.profileActive]}
            >
              <Text style={[styles.profileText, risk === profile && styles.profileTextActive]}>
                {profile.toUpperCase()}
              </Text>
            </Pressable>
          ))}
        </View>
      </MetalPanel>

      <SectionTitle title="Bankroll Guardrails" subtitle={`Current balance $${bankroll?.balance ?? "0.00"}`} />
      <MetalPanel>
        <FormField label="Maximum stake per ticket (%)" value={maxStake} onChangeText={setMaxStake} keyboardType="decimal-pad" />
        <FormField label="Maximum daily exposure (%)" value={dailyExposure} onChangeText={setDailyExposure} keyboardType="decimal-pad" />
        <FormField label="Maximum exposure per thesis (%)" value={thesisExposure} onChangeText={setThesisExposure} keyboardType="decimal-pad" />
        <FormField label="Pause after consecutive losses" value={lossPause} onChangeText={setLossPause} keyboardType="number-pad" />
        <YwpButton label="SAVE PROTECTED CONTROLS" onPress={() => void save()} loading={saving} />
      </MetalPanel>

      <SectionTitle title="Canonical Protocol" subtitle="Visible version prevents fallback to old rules." />
      <MetalPanel tone="success">
        <View style={styles.row}>
          <View style={styles.flex}>
            <Text style={styles.title}>{protocol?.name}</Text>
            <Text style={type.caption}>VERSION {protocol?.version}</Text>
          </View>
          <StatusPill value={protocol?.status ?? "canonical"} />
        </View>
        {(protocol?.constitutional_laws ?? []).map((law) => (
          <Text key={law} style={styles.law}>✓ {law}</Text>
        ))}
      </MetalPanel>

      <SectionTitle title="Removed & Superseded" subtitle="These shortcuts are explicitly blocked." />
      <MetalPanel tone="danger">
        {(protocol?.superseded_or_removed ?? []).map((rule) => (
          <Text key={rule} style={styles.removed}>⛔ {rule}</Text>
        ))}
      </MetalPanel>

      <YwpButton label="SIGN OUT" variant="danger" onPress={() => void signOut()} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: { color: colors.white, fontSize: 20, fontWeight: "900" },
  saved: { color: colors.success, fontWeight: "800" },
  profileRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  profile: {
    flex: 1,
    minWidth: 100,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundRaised,
    borderRadius: radius.md,
    padding: spacing.md,
    alignItems: "center",
  },
  profileActive: { borderColor: colors.gold, backgroundColor: colors.surfaceGold },
  profileText: { color: colors.muted, fontWeight: "900", fontSize: 11 },
  profileTextActive: { color: colors.gold },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1, gap: spacing.xs },
  law: { color: colors.success, fontSize: 13, lineHeight: 20 },
  removed: { color: colors.danger, fontSize: 13, lineHeight: 20 },
});
