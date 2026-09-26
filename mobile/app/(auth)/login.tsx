import { Link, Redirect, router } from "expo-router";
import { useEffect, useState } from "react";
import {
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  View,
} from "react-native";

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
  const [keyboardOpen, setKeyboardOpen] = useState(false);

  useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSub = Keyboard.addListener(showEvent, () => setKeyboardOpen(true));
    const hideSub = Keyboard.addListener(hideEvent, () => setKeyboardOpen(false));
    return () => {
      showSub.remove();
      hideSub.remove();
    };
  }, []);

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
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 12 : 0}
    >
      <Screen contentStyle={styles.content} keyboardAware>
        {!keyboardOpen ? (
          <>
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
          </>
        ) : (
          <View style={styles.compactBrand}>
            <Text style={styles.compactMark}>{brand.product}</Text>
            <Text style={styles.compactHint}>Password field stays above the keys</Text>
          </View>
        )}

        <MotionReveal delay={keyboardOpen ? 0 : 280}>
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
              returnKeyType="next"
            />
            <FormField
              label="Password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete="current-password"
              placeholder="••••••••••"
              returnKeyType="go"
              onSubmitEditing={() => void submit()}
            />
            <YwpButton label="ENTER YWP OS" onPress={() => void submit()} loading={loading} />
            <Link href="/(auth)/register" style={styles.link}>
              Create a protected account
            </Link>
          </MetalPanel>
        </MotionReveal>
        {!keyboardOpen ? (
          <Text style={styles.disclaimer}>
            YWP OS is decision support, not a guarantee. PASS is an official answer.
            Wager responsibly and only where legal.
          </Text>
        ) : null}
      </Screen>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  // Top-aligned so the login panel can scroll above the keyboard in landscape.
  content: { justifyContent: "flex-start", paddingTop: spacing.md, gap: spacing.lg },
  copyStage: {
    gap: spacing.sm,
    paddingVertical: spacing.sm,
    backgroundColor: "transparent",
  },
  compactBrand: {
    gap: 4,
    paddingBottom: spacing.xs,
  },
  compactMark: {
    color: colors.goldBright,
    fontFamily: fonts.display,
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: -0.6,
  },
  compactHint: {
    ...type.caption,
    color: colors.circuitBlueBright,
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
