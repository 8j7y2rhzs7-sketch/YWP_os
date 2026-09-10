import { Link, Redirect, router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { EngineStage } from "@/components/EngineStage";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { MetalPanel } from "@/components/MetalPanel";
import { MetalShimmer } from "@/components/MetalShimmer";
import { MotionReveal } from "@/components/MotionReveal";
import { Screen } from "@/components/Screen";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { ensureApiUrl } from "@/lib/api";
import { brand, colors, fonts, spacing, type } from "@/theme";

export default function LoginScreen() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) {
    return <Redirect href={user.has_app_access ? "/(tabs)" : "/(auth)/paywall"} />;
  }

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      await ensureApiUrl();
      const profile = await login(email, password);
      router.replace(profile.has_app_access ? "/(tabs)" : "/(auth)/paywall");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen contentStyle={styles.content}>
      <MotionReveal fromY={24}>
        <EngineStage size={220} tone="idle" intensity="hero" label="Online" />
      </MotionReveal>

      <MotionReveal delay={140}>
        <View style={styles.copyStage}>
          <MetalShimmer intensity="bright" periodMs={3200} style={styles.brandShimmer}>
            <Text style={styles.brandMark}>{brand.product}</Text>
          </MetalShimmer>
          <Text style={styles.tagline}>YOUR WINNING PROCESS</Text>
          <Text style={styles.heroTitle}>Measure twice.{"\n"}Cut once.</Text>
          <Text style={styles.heroBody}>
            Full sweeps, honest PASS calls, bankroll discipline, and learning from
            every result.
          </Text>
        </View>
      </MotionReveal>

      <MotionReveal delay={280}>
        <MetalPanel tone="gold">
          <Text style={styles.panelTitle}>COMMAND CENTER LOGIN</Text>
          {error ? <ErrorNotice message={error} /> : null}
          <FormField
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            placeholder="you@example.com"
          />
          <FormField
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete="current-password"
            placeholder="••••••••••"
          />
          <YwpButton label="ENTER YWP OS" onPress={() => void submit()} loading={loading} />
          <Link href="/(auth)/register" style={styles.link}>
            Create a protected account
          </Link>
        </MetalPanel>
      </MotionReveal>
      <Text style={styles.disclaimer}>
        YWP OS is decision support, not a guarantee. PASS is an official answer.
        Wager responsibly and only where legal.
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { justifyContent: "center", paddingTop: spacing.md, gap: spacing.xl },
  copyStage: {
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    backgroundColor: "transparent",
  },
  brandShimmer: { alignSelf: "flex-start", borderRadius: 8 },
  brandMark: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 36,
    fontWeight: "800",
    letterSpacing: -1.1,
  },
  tagline: {
    ...type.eyebrow,
    color: colors.circuitBlueBright,
  },
  heroTitle: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 28,
    fontWeight: "800",
    letterSpacing: -0.8,
    lineHeight: 32,
  },
  heroBody: { ...type.body, color: colors.silver },
  panelTitle: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.2,
  },
  link: {
    color: colors.circuitBlueBright,
    textAlign: "center",
    fontFamily: fonts.bodyBold,
    fontSize: 14,
    marginTop: spacing.sm,
  },
  disclaimer: {
    ...type.caption,
    textAlign: "center",
    color: colors.dim,
  },
});
