import { Link, Redirect, router } from "expo-router";
import { useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { brandAssets } from "@/brandAssets";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { MetalPanel } from "@/components/MetalPanel";
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
      {/* Art alone — no UI text on top of the emblem */}
      <View style={styles.emblemStage}>
        <Image
          source={brandAssets.decisionEngineEmblem}
          style={styles.emblem}
          resizeMode="contain"
          accessibilityLabel="YWP Decision Engine emblem"
        />
      </View>

      {/* Clear type on solid stadium night — never over the poster */}
      <View style={styles.copyStage}>
        <Text style={styles.brandMark}>{brand.product}</Text>
        <Text style={styles.tagline}>YOUR WINNING PROCESS</Text>
        <Text style={styles.heroTitle}>Measure twice.{"\n"}Cut once.</Text>
        <Text style={styles.heroBody}>
          Full sweeps, honest PASS calls, bankroll discipline, and learning from
          every result.
        </Text>
      </View>

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
      <Text style={styles.disclaimer}>
        YWP OS is decision support, not a guarantee. PASS is an official answer.
        Wager responsibly and only where legal.
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { justifyContent: "center", paddingTop: spacing.md, gap: spacing.lg },
  emblemStage: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: "rgba(26,168,240,0.4)",
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.md,
  },
  emblem: {
    width: "100%",
    maxWidth: 320,
    height: 280,
  },
  copyStage: {
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    backgroundColor: "transparent",
  },
  brandMark: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 42,
    fontWeight: "800",
    letterSpacing: -0.4,
  },
  tagline: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 2.4,
  },
  heroTitle: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 34,
    fontWeight: "800",
    lineHeight: 38,
    letterSpacing: -0.7,
    marginTop: spacing.xs,
  },
  heroBody: { ...type.body, color: colors.silver, maxWidth: 580 },
  panelTitle: {
    color: colors.gold,
    fontFamily: fonts.displaySemi,
    fontSize: 18,
    fontWeight: "700",
  },
  link: {
    color: colors.gold,
    textAlign: "center",
    fontFamily: fonts.bodyBold,
    fontWeight: "700",
    padding: spacing.sm,
  },
  disclaimer: { ...type.caption, textAlign: "center", padding: spacing.lg },
});
