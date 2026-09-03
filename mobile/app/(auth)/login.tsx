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
import { colors, spacing, type } from "@/theme";

export default function LoginScreen() {
  const { user, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) {
    return <Redirect href={user.has_app_access ? "/(tabs)" : "/(auth)/paywall"} />;
  }

  async function submit(nextEmail = email, nextPassword = password) {
    setLoading(true);
    setError(null);
    try {
      await ensureApiUrl();
      await login(nextEmail, nextPassword);
      router.replace("/(tabs)");
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
        <Text style={type.eyebrow}>DECISION INTELLIGENCE</Text>
        <Text style={styles.heroTitle}>Measure twice. Cut once.</Text>
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
        <YwpButton
          label="USE SAFE DEMO ACCOUNT"
          variant="outline"
          onPress={() => void submit("demo@ywp-os.com", "YwpDemo!2026")}
          disabled={loading}
        />
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
  heroTitle: { color: colors.white, fontSize: 36, fontWeight: "900" },
  heroBody: { ...type.body, color: colors.silver, maxWidth: 580 },
  panelTitle: { color: colors.gold, fontSize: 18, fontWeight: "900" },
  link: {
    color: colors.gold,
    textAlign: "center",
    fontWeight: "800",
    padding: spacing.sm,
  },
  disclaimer: { ...type.caption, textAlign: "center", padding: spacing.lg },
});
