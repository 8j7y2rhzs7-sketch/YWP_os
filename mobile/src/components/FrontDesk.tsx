import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { MetalPanel } from "@/components/MetalPanel";
import { SectionTitle } from "@/components/SectionTitle";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { colors, fonts, spacing, type } from "@/theme";
import type { FrontDesk as FrontDeskState } from "@/types";

const POLL_MS = 20_000;

function openDeskRoute(route: string) {
  if (route === "/ready") {
    router.push("/ready");
    return;
  }
  if (route === "/(tabs)/slate") {
    router.push("/(tabs)/slate");
    return;
  }
  if (route.startsWith("/ticket/")) {
    const id = route.slice("/ticket/".length);
    if (id) {
      router.push(`/ticket/${id}`);
      return;
    }
  }
  router.push("/(tabs)/slate");
}

export function FrontDesk() {
  const { request } = useAuth();
  const [desk, setDesk] = useState<FrontDeskState | null>(null);
  const [quiet, setQuiet] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await request<FrontDeskState>("/desk");
      setDesk(next);
      setQuiet(false);
    } catch {
      setQuiet(true);
    }
  }, [request]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const status = desk?.ready_status;
    if (status !== "pricing" && status !== "scheduled") return;
    const timer = setInterval(() => {
      void load();
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [desk?.ready_status, load]);

  return (
    <View>
      <SectionTitle
        title="Front desk"
        subtitle="One next step from the board and your tickets."
      />
      <MetalPanel tone="gold" accent={colors.circuitBlue}>
        {desk ? (
          <View style={styles.copy}>
            <Text style={styles.headline}>{desk.headline}</Text>
            <Text style={type.body}>{desk.detail}</Text>
            <View style={styles.beats}>
              {desk.beats.map((beat) => (
                <View key={beat.phase} style={styles.beat}>
                  <Text style={styles.beatPhase}>{beat.phase}</Text>
                  <Text style={styles.beatText}>{beat.text}</Text>
                </View>
              ))}
            </View>
            <YwpButton
              label={desk.primary.label}
              onPress={() => openDeskRoute(desk.primary.route)}
            />
            {desk.secondary ? (
              <YwpButton
                label={desk.secondary.label}
                variant="outline"
                onPress={() => openDeskRoute(desk.secondary?.route ?? "/ready")}
              />
            ) : null}
            <Text style={styles.notice}>{desk.notice}</Text>
          </View>
        ) : (
          <Text style={type.body}>
            {quiet
              ? "Front desk is warming. Ready plays and Run are still right here."
              : "Checking where you are in the day."}
          </Text>
        )}
      </MetalPanel>
    </View>
  );
}

const styles = StyleSheet.create({
  copy: { gap: spacing.md },
  headline: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: -0.35,
    lineHeight: 26,
  },
  beats: { flexDirection: "row", gap: spacing.sm },
  beat: {
    flex: 1,
    gap: spacing.xs,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: 12,
    backgroundColor: colors.glass,
  },
  beatPhase: {
    color: colors.circuitBlueBright,
    fontFamily: fonts.bodyBold,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1.1,
    textTransform: "uppercase",
  },
  beatText: {
    color: colors.silver,
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    lineHeight: 16,
  },
  notice: {
    ...type.caption,
    color: colors.dim,
  },
});
