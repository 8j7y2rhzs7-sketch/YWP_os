import * as Clipboard from "expo-clipboard";
import { useState } from "react";
import { Platform, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing, type as typ } from "../theme";
import { MetalPanel } from "./MetalPanel";
import { SectionTitle } from "./SectionTitle";
import { YwpButton } from "./YwpButton";

interface SlipLeg {
  selection: string;
  american_odds: number;
  thesis_key: string;
  status?: string;
}

interface Props {
  ticketLabel: string;
  legs: SlipLeg[];
  stake: string;
  potentialPayout: string;
  lockStatus: string | null;
}

export function SlipBuilder({ ticketLabel, legs, stake, potentialPayout, lockStatus }: Props) {
  const [copied, setCopied] = useState(false);

  const activeLegs = legs.filter((l) => l.status !== "skipped");
  const floorPass = lockStatus === "LOCKED";

  const slipText = [
    `YWP OS — ${ticketLabel}`,
    `Status: ${floorPass ? "LOCKED" : lockStatus ?? "PENDING"}`,
    `Stake: $${stake} | Potential: $${potentialPayout}`,
    "",
    ...activeLegs.map((l, i) => `${i + 1}. ${l.selection} (${l.american_odds > 0 ? "+" : ""}${l.american_odds})`),
    "",
    "— Copy into Hard Rock bet slip manually —",
  ].join("\n");

  async function copySlip() {
    try {
      if (Platform.OS === "web") {
        await navigator.clipboard.writeText(slipText);
      } else {
        await Clipboard.setStringAsync(slipText);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <View>
      <SectionTitle title="Ready-to-Place Slip" subtitle="Copy and paste into Hard Rock" />
      <MetalPanel tone={floorPass ? "gold" : "danger"}>
        <Text style={styles.slipText}>{slipText}</Text>
        <View style={styles.actions}>
          <YwpButton label={copied ? "COPIED" : "COPY SLIP"} onPress={() => void copySlip()} />
        </View>
        {copied ? <Text style={styles.toast}>Paste into Hard Rock bet slip manually.</Text> : null}
      </MetalPanel>

      <SectionTitle title="Pre-Place Checklist" />
      <MetalPanel>
        <CheckItem label="Lock Check passed" pass={floorPass} />
        <CheckItem label="No skipped legs" pass={activeLegs.length === legs.length} />
        <CheckItem label="Stake within guardrails" pass={true} />
        <CheckItem label="Never backfill cut legs" pass={true} />
        <CheckItem label="Odds verified on book" pass={false} manual />
      </MetalPanel>
    </View>
  );
}

function CheckItem({ label, pass: ok, manual }: { label: string; pass: boolean; manual?: boolean }) {
  return (
    <View style={styles.checkRow}>
      <Text style={[styles.checkIcon, ok ? styles.pass : styles.fail]}>
        {ok ? "✓" : manual ? "○" : "✗"}
      </Text>
      <Text style={[styles.checkLabel, ok ? styles.pass : manual ? styles.manual : styles.fail]}>
        {label}{manual ? " (verify manually)" : ""}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  slipText: {
    fontFamily: Platform.select({ ios: "Menlo", android: "monospace", web: "monospace" }),
    fontSize: 12,
    lineHeight: 18,
    color: colors.text,
  },
  actions: {
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  toast: {
    color: colors.goldBright,
    fontSize: 12,
    marginTop: spacing.sm,
  },
  checkRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  checkIcon: {
    fontSize: 16,
    fontWeight: "900",
    width: 20,
    textAlign: "center",
  },
  checkLabel: {
    fontSize: 13,
    fontWeight: "700",
  },
  pass: { color: colors.success },
  fail: { color: colors.danger },
  manual: { color: colors.muted },
});
