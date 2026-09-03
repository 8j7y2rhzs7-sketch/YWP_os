import { useCallback, useState } from "react";
import { Linking, StyleSheet, Text, View } from "react-native";
import { Redirect } from "expo-router";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { MetalPanel } from "@/components/MetalPanel";
import { Screen } from "@/components/Screen";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { ApiError, WHOP_CHECKOUT_URL } from "@/lib/api";
import type { SubscriptionStatus } from "@/types";
import { brand, colors, spacing, type } from "@/theme";

export default function PaywallScreen() {
  const { user, loading, logout, reloadUser, request } = useAuth();
  const [busy, setBusy] = useState<"sync" | "checkout" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openCheckout = useCallback(async () => {
    setBusy("checkout");
    setError(null);
    try {
      const checkout = await request<{ checkout_url: string; message: string }>(
        "/whop/checkout",
      ).catch(() => ({ checkout_url: WHOP_CHECKOUT_URL, message: "" }));
      const opened = await Linking.openURL(checkout.checkout_url || WHOP_CHECKOUT_URL);
      if (!opened) {
        setError("Could not open Whop checkout. Copy the link from your browser.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Checkout link unavailable");
    } finally {
      setBusy(null);
    }
  }, [request]);

  const syncAccess = useCallback(async () => {
    setBusy("sync");
    setError(null);
    try {
      const status = await request<SubscriptionStatus>("/whop/sync", {
        method: "POST",
      });
      if (status.has_access) {
        await reloadUser();
      } else {
        setError(
          "No active Whop subscription found for this email. Subscribe first, then sync again.",
        );
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sync subscription");
    } finally {
      setBusy(null);
    }
  }, [reloadUser, request]);

  if (loading) return null;
  if (!user) return <Redirect href="/(auth)/login" />;
  if (user.has_app_access) return <Redirect href="/(tabs)" />;

  return (
    <Screen>
      <BrandHeader title="Membership Required" subtitle={brand.descriptor} />
      <MetalPanel style={styles.panel}>
        <Text style={type.section}>Unlock YWP OS</Text>
        <Text style={type.body}>
          YWP OS is Daily Access on Whop — DECISION ENGINE, $25 for 1 day.
          Pay on Whop with the same email as this account, then sync access.
          All payments stay on Whop.
        </Text>
        <View style={styles.steps}>
          <Text style={styles.step}>1. Tap Subscribe on Whop</Text>
          <Text style={styles.step}>2. Complete checkout</Text>
          <Text style={styles.step}>3. Return and tap Sync my access</Text>
        </View>
        {error ? <ErrorNotice message={error} /> : null}
        <YwpButton
          label="Subscribe on Whop"
          onPress={() => void openCheckout()}
          loading={busy === "checkout"}
        />
        <YwpButton
          label="Sync my access"
          variant="outline"
          onPress={() => void syncAccess()}
          loading={busy === "sync"}
        />
        <YwpButton label="Sign out" variant="outline" onPress={() => void logout()} />
        <Text style={type.caption}>
          Signed in as {user.email}. Status: {user.subscription_status}
        </Text>
      </MetalPanel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  panel: { gap: spacing.lg, marginTop: spacing.xl },
  steps: { gap: spacing.sm },
  step: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
  },
});
