import { Link, Redirect, router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text } from "react-native";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { FormField } from "@/components/FormField";
import { MetalPanel } from "@/components/MetalPanel";
import { Screen } from "@/components/Screen";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { colors, spacing, type } from "@/theme";

export default function RegisterScreen() {
  const { user, register } = useAuth();
  const [name, setName] = useState("");
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
      await register({ name, email, password });
      router.replace("/(auth)/paywall");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen contentStyle={styles.content}>
      <BrandHeader title="CREATE ACCOUNT" compact />
      <MetalPanel tone="gold">
        <Text style={styles.title}>YOUR PROCESS. YOUR DATA.</Text>
        <Text style={type.caption}>
          Recommendations, tickets, results, and learning history remain scoped to
          your authenticated account.
        </Text>
        {error ? <ErrorNotice message={error} /> : null}
        <FormField
          label="Display name"
          value={name}
          onChangeText={setName}
          autoComplete="name"
          placeholder="GHOSTT YWP"
        />
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
          autoComplete="new-password"
          placeholder="10+ chars, upper/lower/number/symbol"
        />
        <YwpButton label="CREATE YWP ACCOUNT" onPress={() => void submit()} loading={loading} />
        <Link href="/(auth)/login" style={styles.link}>
          Back to login
        </Link>
      </MetalPanel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { justifyContent: "center", paddingTop: spacing.xl },
  title: { color: colors.gold, fontSize: 20, fontWeight: "900" },
  link: {
    color: colors.gold,
    textAlign: "center",
    fontWeight: "800",
    padding: spacing.sm,
  },
});
