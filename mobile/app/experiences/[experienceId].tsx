import { Redirect, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Linking } from "react-native";

import { LoadingState } from "@/components/LoadingState";
import { Screen } from "@/components/Screen";
import { useAuth } from "@/context/AuthContext";
import { WHOP_CHECKOUT_URL } from "@/lib/api";

export default function ExperienceScreen() {
  const { experienceId } = useLocalSearchParams<{ experienceId: string }>();
  const { user, loading, request } = useAuth();
  const [checkout, setCheckout] = useState<string | null>(null);

  useEffect(() => {
    if (loading) return;
    if (user?.has_app_access) return;
    void (async () => {
      try {
        const gate = await request<{ has_access: boolean; checkout_url: string }>(
          "/whop/gate",
        );
        if (!gate.has_access) {
          setCheckout(gate.checkout_url || WHOP_CHECKOUT_URL);
          await Linking.openURL(gate.checkout_url || WHOP_CHECKOUT_URL);
        }
      } catch {
        setCheckout(WHOP_CHECKOUT_URL);
        await Linking.openURL(WHOP_CHECKOUT_URL);
      }
    })();
  }, [loading, request, user?.has_app_access, experienceId]);

  if (loading) {
    return (
      <Screen scroll={false} contentStyle={{ justifyContent: "center" }}>
        <LoadingState label="Checking DECISION ENGINE access…" />
      </Screen>
    );
  }
  if (user?.has_app_access) return <Redirect href="/(tabs)" />;
  if (!user) return <Redirect href="/(auth)/login" />;
  if (checkout) return <Redirect href="/(auth)/paywall" />;
  return (
    <Screen scroll={false} contentStyle={{ justifyContent: "center" }}>
      <LoadingState label="Checking DECISION ENGINE access…" />
    </Screen>
  );
}
