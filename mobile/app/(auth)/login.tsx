import { Link, Redirect, router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { MetalPanel } from "@/components/MetalPanel";
import { Screen } from "@/components/Screen";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { ensureApiUrl } from "@/lib/api";
import { colors, fonts, spacing, type } from "@/theme";

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
      <BrandHeader />
      <View style={styles.hero}>
        <Text style={styles.brandMark}>YWP OS</Text>
        <Text style={type.eyebrow}>DECISION INTELLIGENCE</Text>
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
  content: { justifyContent: "center", paddingTop: spacing.xl },
  hero: { gap: spacing.sm, paddingVertical: spacing.xl },
  brandMark: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 18,
    fontWeight: "800",
    letterSpacing: 3.2,
  },
  heroTitle: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 40,
    fontWeight: "800",
    lineHeight: 44,
    letterSpacing: -0.8,
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
