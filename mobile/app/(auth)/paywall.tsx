import * as Clipboard from "expo-clipboard";
import { useCallback, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { Redirect } from "expo-router";

import { BrandHeader } from "@/components/BrandHeader";
import { ErrorNotice } from "@/components/ErrorNotice";
import { MetalPanel } from "@/components/MetalPanel";
import { Screen } from "@/components/Screen";
import { YwpButton } from "@/components/YwpButton";
import { useAuth } from "@/context/AuthContext";
import { ApiError, APP_DOWNLOAD_URL, WHOP_CHECKOUT_URL } from "@/lib/api";
import type { SubscriptionStatus } from "@/types";
import { brand, colors, fonts, spacing, type } from "@/theme";

export default function PaywallScreen() {
  const { user, loading, logout, reloadUser, request } = useAuth();
  const [busy, setBusy] = useState<"sync" | "checkout" | "download" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState(APP_DOWNLOAD_URL);

  const openCheckout = useCallback(async () => {
    setBusy("checkout");
    setError(null);
    setNote(null);
    try {
      const checkout = await request<{
        checkout_url: string;
        app_download_url?: string | null;
        message: string;
      }>("/whop/checkout").catch(() => ({
        checkout_url: WHOP_CHECKOUT_URL,
        app_download_url: APP_DOWNLOAD_URL,
        message: "",
      }));
      if (checkout.app_download_url) setDownloadUrl(checkout.app_download_url);
      const opened = await Linking.openURL(checkout.checkout_url || WHOP_CHECKOUT_URL);
      if (!opened) {
        setError("Could not open Whop checkout. Copy the link from your browser.");
      } else {
        setNote("After paying on Whop with this email, return here and Sync my access.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Checkout link unavailable");
    } finally {
      setBusy(null);
    }
  }, [request]);

  const openDownload = useCallback(async () => {
    setBusy("download");
    setError(null);
    setNote(null);
    try {
      const checkout = await request<{
        app_download_url?: string | null;
      }>("/whop/checkout").catch(() => ({ app_download_url: downloadUrl }));
      const url = checkout.app_download_url || downloadUrl || APP_DOWNLOAD_URL;
      setDownloadUrl(url);
      const opened = await Linking.openURL(url);
      if (!opened) {
        await Clipboard.setStringAsync(url);
        setNote("APK link copied. Use it to update or reinstall, then open this app again.");
      } else {
        setNote("APK link opened. Use it only for update/reinstall — you already have the app.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Download link unavailable");
    } finally {
      setBusy(null);
    }
  }, [downloadUrl, request]);

  const syncAccess = useCallback(async () => {
    setBusy("sync");
    setError(null);
    setNote(null);
    try {
      const status = await request<SubscriptionStatus>("/whop/sync", {
        method: "POST",
      });
      if (status.app_download_url) setDownloadUrl(status.app_download_url);
      if (status.has_access) {
        await reloadUser();
      } else {
        setError(
          `No active Whop membership for ${user?.email ?? "this email"}. ` +
            "Pay on Whop with this exact email, then sync again.",
        );
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sync subscription");
    } finally {
      setBusy(null);
    }
  }, [reloadUser, request, user?.email]);

  if (loading) return null;
  if (!user) return <Redirect href="/(auth)/login" />;
  if (user.has_app_access) return <Redirect href="/(tabs)" />;

  return (
    <Screen>
      <BrandHeader title="Membership Required" subtitle={brand.descriptor} />
      <MetalPanel style={styles.panel}>
        <Text style={type.section}>Unlock YWP OS</Text>
        <Text style={type.body}>
          Daily Access is billed on Whop — DECISION ENGINE, $25 for 1 day. Whop
          auto-expires the membership after 24 hours. This app re-checks Whop
          regularly; unlock is never permanent. After it expires, pay again with
          the same email and Sync to reopen.
        </Text>
        <View style={styles.steps}>
          <Text style={styles.step}>1. Subscribe on Whop (use {user.email})</Text>
          <Text style={styles.step}>2. Return here and Sync my access</Text>
        </View>
        {error ? <ErrorNotice message={error} /> : null}
        {note ? <Text style={styles.note}>{note}</Text> : null}
        <YwpButton
          label="1. Subscribe on Whop"
          onPress={() => void openCheckout()}
          loading={busy === "checkout"}
        />
        <YwpButton
          label="2. Sync my access"
          variant="outline"
          onPress={() => void syncAccess()}
          loading={busy === "sync"}
        />
        <Pressable
          onPress={() => void openDownload()}
          disabled={busy === "download"}
          accessibilityRole="link"
        >
          <Text style={styles.secondaryLink}>
            {busy === "download" ? "Opening APK link…" : "Need an update or reinstall? Get APK"}
          </Text>
        </Pressable>
        <YwpButton label="Sign out" variant="outline" onPress={() => void logout()} />
        <Text style={type.caption}>
          Signed in as {user.email}. Status: {user.subscription_status}. No
          separate license key — membership email must match this login. First-time
          buyers get the APK from Whop after payment; this screen is for unlock after
          install.
        </Text>
      </MetalPanel>
    </Screen>
  );
}

const styles = StyleSheet.create({
  panel: { gap: spacing.lg, marginTop: spacing.xl },
  steps: { gap: spacing.sm },
  step: { ...type.body, color: colors.silver },
  note: { ...type.caption, color: colors.gold },
  secondaryLink: {
    ...type.caption,
    color: colors.gold,
    textAlign: "center",
    fontFamily: fonts.bodyBold,
    fontWeight: "700",
    paddingVertical: spacing.sm,
  },
});
