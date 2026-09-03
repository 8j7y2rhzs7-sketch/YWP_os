import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Alert, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

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
import { getApiUrl, PRODUCTION_API_URL } from "@/lib/api";
import { submitErrorReport } from "@/lib/errorReporting";
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
  const [txnAmount, setTxnAmount] = useState("");
  const [txnLoading, setTxnLoading] = useState(false);
  const [txnMsg, setTxnMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [reportText, setReportText] = useState("");
  const [reportCategory, setReportCategory] = useState<"pick_quality" | "ticket_build" | "ui" | "data" | "other">("pick_quality");
  const [reportLoading, setReportLoading] = useState(false);
  const [reportMsg, setReportMsg] = useState<string | null>(null);
  const apiUrl = getApiUrl() || PRODUCTION_API_URL;

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

  async function submitTxn(txnType: "deposit" | "withdrawal") {
    const amt = parseFloat(txnAmount);
    if (!amt || amt <= 0) {
      setTxnMsg("Enter a valid amount.");
      return;
    }
    setTxnLoading(true);
    setTxnMsg(null);
    try {
      await request("/bankroll/transaction", {
        method: "POST",
        body: JSON.stringify({ transaction_type: txnType, amount: amt.toFixed(2) }),
      });
      setTxnAmount("");
      await load();
      setTxnMsg(`${txnType === "deposit" ? "Deposit" : "Withdrawal"} of $${amt.toFixed(2)} recorded.`);
    } catch (reason) {
      setTxnMsg(reason instanceof Error ? reason.message : "Transaction failed");
    } finally {
      setTxnLoading(false);
    }
  }

  async function submitReport() {
    const message = reportText.trim();
    if (message.length < 3) {
      setReportMsg("Tell us what looked wrong (at least a few words).");
      return;
    }
    setReportLoading(true);
    setReportMsg(null);
    try {
      await submitErrorReport({
        category: reportCategory,
        message,
        screen: "settings",
        context: { source: "manual_settings_report" },
      });
      setReportText("");
      setReportMsg("Report sent. We will use it to fix the live app.");
    } catch (reason) {
      setReportMsg(reason instanceof Error ? reason.message : "Could not send report");
    } finally {
      setReportLoading(false);
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

      <SectionTitle
        title="API Server"
        subtitle="This build connects automatically to the live YWP OS backend."
      />
      <MetalPanel tone="success">
        <Text style={type.eyebrow}>CONNECTED</Text>
        <Text style={styles.title}>{apiUrl}</Text>
        <Text style={type.caption}>
          No URL entry required. The production address is built into the app.
        </Text>
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

      <SectionTitle title="Bankroll" subtitle={`Current balance $${bankroll?.balance ?? "0.00"}`} />
      <MetalPanel>
        <View style={styles.txnRow}>
          <TextInput
            style={styles.txnInput}
            placeholder="Amount"
            placeholderTextColor={colors.muted}
            keyboardType="decimal-pad"
            value={txnAmount}
            onChangeText={setTxnAmount}
          />
          <YwpButton
            label="DEPOSIT"
            onPress={() => void submitTxn("deposit")}
            style={styles.txnBtn}
            loading={txnLoading}
          />
          <YwpButton
            label="WITHDRAW"
            variant="danger"
            onPress={() => void submitTxn("withdrawal")}
            style={styles.txnBtn}
            loading={txnLoading}
          />
        </View>
        {txnMsg ? <Text style={styles.txnMsg}>{txnMsg}</Text> : null}
      </MetalPanel>

      <SectionTitle title="Bankroll Guardrails" />
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

      <SectionTitle title="Responsible Gaming" subtitle="Your well-being comes first." />
      <MetalPanel tone="danger">
        <Text style={styles.rgText}>
          If gambling is no longer fun, take a break. You are always in control.
        </Text>
        <YwpButton
          label="NATIONAL PROBLEM GAMBLING HELPLINE"
          variant="outline"
          onPress={() => {
            if (typeof window !== "undefined" && window.open) {
              window.open("tel:1-800-522-4700");
            } else {
              Alert.alert("Helpline", "Call 1-800-522-4700 (24/7, confidential).");
            }
          }}
        />
        <Text style={styles.rgCaption}>1-800-522-4700 — Available 24/7, free & confidential</Text>
      </MetalPanel>

      <SectionTitle
        title="Report a Problem"
        subtitle="After you use the app, tell us what broke or felt wrong so we can fix it."
      />
      <MetalPanel>
        <View style={styles.profileRow}>
          {(
            [
              ["pick_quality", "PICKS"],
              ["ticket_build", "CARDS"],
              ["data", "DATA"],
              ["ui", "UI"],
              ["other", "OTHER"],
            ] as const
          ).map(([value, label]) => (
            <Pressable
              key={value}
              onPress={() => setReportCategory(value)}
              style={[styles.profile, reportCategory === value && styles.profileActive]}
            >
              <Text style={[styles.profileText, reportCategory === value && styles.profileTextActive]}>
                {label}
              </Text>
            </Pressable>
          ))}
        </View>
        <FormField
          label="What went wrong?"
          value={reportText}
          onChangeText={setReportText}
          placeholder="Example: #1 pick never showed on Max Bet / cards looked off"
        />
        <YwpButton
          label="SEND ERROR REPORT"
          onPress={() => void submitReport()}
          loading={reportLoading}
        />
        {reportMsg ? <Text style={styles.txnMsg}>{reportMsg}</Text> : null}
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
  rgText: { color: colors.danger, fontSize: 14, fontWeight: "700", lineHeight: 20, marginBottom: spacing.sm },
  rgCaption: { ...type.caption, textAlign: "center", marginTop: spacing.sm },
  txnRow: { flexDirection: "row", gap: spacing.sm, alignItems: "center", flexWrap: "wrap" },
  txnInput: {
    flex: 1,
    minWidth: 100,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundRaised,
    borderRadius: radius.md,
    padding: spacing.md,
    color: colors.white,
    fontWeight: "700",
    fontSize: 16,
  },
  txnBtn: { minWidth: 90 },
  txnMsg: { color: colors.goldBright, fontSize: 13, marginTop: spacing.sm },
});
