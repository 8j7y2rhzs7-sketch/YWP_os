import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useFonts, Syne_700Bold, Syne_800ExtraBold } from "@expo-google-fonts/syne";
import {
  DMSans_400Regular,
  DMSans_500Medium,
  DMSans_700Bold,
} from "@expo-google-fonts/dm-sans";
import * as SplashScreen from "expo-splash-screen";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { BootSequence } from "@/components/BootSequence";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { OfflineNotice } from "@/components/OfflineNotice";
import { AppDataProvider } from "@/context/AppDataContext";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { colors, fonts } from "@/theme";

SplashScreen.preventAutoHideAsync().catch(() => undefined);

function ScopedAppData({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return <AppDataProvider userId={user?.id ?? null}>{children}</AppDataProvider>;
}

export default function RootLayout() {
  const [loaded, fontError] = useFonts({
    Syne_700Bold,
    Syne_800ExtraBold,
    DMSans_400Regular,
    DMSans_500Medium,
    DMSans_700Bold,
  });
  const [bootDone, setBootDone] = useState(false);
  const fontsReady = loaded || Boolean(fontError);

  useEffect(() => {
    SplashScreen.hideAsync().catch(() => undefined);
  }, []);

  const finishBoot = useCallback(() => setBootDone(true), []);

  if (!bootDone) {
    return (
      <BootSequence
        ready={fontsReady}
        fontError={fontError ?? null}
        onDone={finishBoot}
      />
    );
  }

  return (
    <ErrorBoundary>
      <AuthProvider>
        <ScopedAppData>
          <StatusBar style="light" />
          <OfflineNotice />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: colors.backgroundRaised },
              headerTintColor: colors.gold,
              headerTitleStyle: {
                color: colors.white,
                fontFamily: fonts.displaySemi,
                fontWeight: "700",
              },
              contentStyle: { backgroundColor: colors.background },
              animation: "fade_from_bottom",
            }}
          >
            <Stack.Screen name="index" options={{ headerShown: false }} />
            <Stack.Screen name="(auth)" options={{ headerShown: false }} />
            <Stack.Screen name="experiences/[experienceId]" options={{ headerShown: false }} />
            <Stack.Screen name="analysis/[id]" options={{ title: "YWP Decision Board" }} />
            <Stack.Screen name="ticket/[id]" options={{ title: "Ticket Lock Center" }} />
            <Stack.Screen name="result/[id]" options={{ title: "Result & Process Grade" }} />
            <Stack.Screen name="log-result" options={{ title: "Log Book Result" }} />
            <Stack.Screen name="share-card" options={{ title: "YWP Graphic Studio" }} />
          </Stack>
        </ScopedAppData>
      </AuthProvider>
    </ErrorBoundary>
  );
}
