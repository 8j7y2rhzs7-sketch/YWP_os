import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AppDataProvider } from "@/context/AppDataContext";
import { AuthProvider } from "@/context/AuthContext";
import { colors } from "@/theme";

export default function RootLayout() {
  return (
    <ErrorBoundary>
    <AuthProvider>
      <AppDataProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: colors.backgroundRaised },
            headerTintColor: colors.gold,
            headerTitleStyle: { color: colors.white, fontWeight: "800" },
            contentStyle: { backgroundColor: colors.background },
            animation: "slide_from_right",
          }}
        >
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="(auth)" options={{ headerShown: false }} />
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen
            name="analysis/[id]"
            options={{ title: "YWP Decision Board" }}
          />
          <Stack.Screen
            name="ticket/[id]"
            options={{ title: "Ticket Lock Center" }}
          />
          <Stack.Screen
            name="result/[id]"
            options={{ title: "Result & Process Grade" }}
          />
          <Stack.Screen
            name="share-card"
            options={{ title: "YWP Graphic Studio" }}
          />
        </Stack>
      </AppDataProvider>
    </AuthProvider>
    </ErrorBoundary>
  );
}
