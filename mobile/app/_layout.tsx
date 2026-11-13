import { Stack, router, usePathname, type Href } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useFonts, Syne_700Bold, Syne_800ExtraBold } from "@expo-google-fonts/syne";
import {
  DMSans_400Regular,
  DMSans_500Medium,
  DMSans_700Bold,
} from "@expo-google-fonts/dm-sans";
import * as SplashScreen from "expo-splash-screen";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { AppState, useColorScheme } from "react-native";
import { enableFreeze } from "react-native-screens";

import { BootSequence } from "@/components/BootSequence";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { OfflineNotice } from "@/components/OfflineNotice";
import { StayAwake } from "@/components/StayAwake";
import { AppDataProvider } from "@/context/AppDataContext";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import { loadSession, rememberSession } from "@/lib/session";
import { colors, fonts } from "@/theme";

// Frozen screens come back blank after the display turns off on Android.
enableFreeze(false);

SplashScreen.preventAutoHideAsync().catch(() => undefined);

/** Survives an activity recreate in the same JS runtime so the boot film does not replay. */
let sessionWarmed = false;
let restoredThisProcess = false;

const LANDING = new Set(["/", "/index", "/(tabs)", "/(tabs)/", "/(tabs)/index"]);

function ReturnToSession() {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const pathnameRef = useRef(pathname);
  pathnameRef.current = pathname;

  useEffect(() => {
    if (!pathname || LANDING.has(pathname)) return;
    rememberSession({ pathname });
  }, [pathname]);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state !== "background") return;
      const current = pathnameRef.current;
      if (current && !LANDING.has(current)) rememberSession({ pathname: current });
    });
    return () => sub.remove();
  }, []);

  useEffect(() => {
    if (loading || !user || restoredThisProcess) return;
    if (!LANDING.has(pathname)) {
      restoredThisProcess = true;
      return;
    }
    restoredThisProcess = true;
    void loadSession().then((session) => {
      const target = session?.pathname;
      if (!target || LANDING.has(target) || target.startsWith("/(auth)")) return;
      router.replace(target as Href);
    });
  }, [loading, pathname, user]);

  return null;
}

function ScopedAppData({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return <AppDataProvider userId={user?.id ?? null}>{children}</AppDataProvider>;
}

function ThemedStack() {
  const scheme = useColorScheme();
  return (
    <>
      <StatusBar style={scheme === "light" ? "dark" : "light"} />
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
        <Stack.Screen
          name="(tabs)"
          options={{ headerShown: false, title: "Home" }}
        />
        <Stack.Screen name="experiences/[experienceId]" options={{ headerShown: false }} />
        <Stack.Screen
          name="analysis/[id]"
          options={{ title: "YWP Decision Board", headerBackTitle: "Home" }}
        />
        <Stack.Screen
          name="ticket/[id]"
          options={{ title: "Ticket Lock Center", headerBackTitle: "Home" }}
        />
        <Stack.Screen
          name="result/[id]"
          options={{ title: "Result & Process Grade", headerBackTitle: "Home" }}
        />
        <Stack.Screen
          name="log-result"
          options={{ title: "Log Book Result", headerBackTitle: "Home" }}
        />
        <Stack.Screen
          name="share-card"
          options={{ title: "YWP Graphic Studio", headerBackTitle: "Home" }}
        />
        <Stack.Screen
          name="market/[id]"
          options={{ title: "Market Call", headerBackTitle: "Markets" }}
        />
      </Stack>
    </>
  );
}

function RootBody() {
  const [loaded, fontError] = useFonts({
    Syne_700Bold,
    Syne_800ExtraBold,
    DMSans_400Regular,
    DMSans_500Medium,
    DMSans_700Bold,
  });
  const [bootDone, setBootDone] = useState(sessionWarmed);
  const fontsReady = loaded || Boolean(fontError);

  useEffect(() => {
    SplashScreen.hideAsync().catch(() => undefined);
  }, []);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        SplashScreen.hideAsync().catch(() => undefined);
      }
    });
    return () => sub.remove();
  }, []);

  const finishBoot = useCallback(() => {
    sessionWarmed = true;
    setBootDone(true);
  }, []);

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
          <ReturnToSession />
          <ThemedStack />
        </ScopedAppData>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default function RootLayout() {
  return (
    <ThemeProvider>
      <StayAwake />
      <RootBody />
    </ThemeProvider>
  );
}
