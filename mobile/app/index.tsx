import { Redirect } from "expo-router";

import { LoadingState } from "@/components/LoadingState";
import { Screen } from "@/components/Screen";
import { useAuth } from "@/context/AuthContext";

export default function Index() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <Screen scroll={false} contentStyle={{ justifyContent: "center" }}>
        <LoadingState label="Loading YWP OS…" />
      </Screen>
    );
  }
  return <Redirect href={user ? (user.has_app_access ? "/(tabs)" : "/(auth)/paywall") : "/(auth)/login"} />;
}
