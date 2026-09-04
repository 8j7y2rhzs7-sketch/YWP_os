import { MaterialCommunityIcons } from "@expo/vector-icons";
import { Redirect, Tabs } from "expo-router";
import type { ComponentProps } from "react";
import { StyleSheet, type ColorValue } from "react-native";

import { useAuth } from "@/context/AuthContext";
import { colors, fonts } from "@/theme";

type IconName = ComponentProps<typeof MaterialCommunityIcons>["name"];

function icon(name: IconName) {
  return function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return <MaterialCommunityIcons name={name} color={color as string} size={size} />;
  };
}

export default function TabLayout() {
  const { user, loading } = useAuth();
  if (!loading && !user) return <Redirect href="/(auth)/login" />;
  if (!loading && user && !user.has_app_access) return <Redirect href="/(auth)/paywall" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.gold,
        tabBarInactiveTintColor: colors.dim,
        tabBarStyle: {
          backgroundColor: "rgba(10,13,18,0.96)",
          borderTopColor: "rgba(196,152,42,0.35)",
          borderTopWidth: StyleSheet.hairlineWidth,
          height: 74,
          paddingTop: 8,
          paddingBottom: 10,
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontFamily: fonts.bodyBold,
          fontWeight: "700",
          letterSpacing: 0.4,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Command", tabBarIcon: icon("shield-crown-outline") }}
      />
      <Tabs.Screen
        name="slate"
        options={{ title: "Run", tabBarIcon: icon("chart-timeline-variant-shimmer") }}
      />
      <Tabs.Screen
        name="tickets"
        options={{ title: "Tickets", tabBarIcon: icon("ticket-confirmation-outline") }}
      />
      <Tabs.Screen
        name="learning"
        options={{ title: "Learning", tabBarIcon: icon("brain") }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: "Controls", tabBarIcon: icon("tune-variant") }}
      />
    </Tabs>
  );
}
