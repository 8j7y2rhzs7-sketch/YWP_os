import { MaterialCommunityIcons } from "@expo/vector-icons";
import { Redirect, Tabs } from "expo-router";
import type { ComponentProps } from "react";
import type { ColorValue } from "react-native";

import { useAuth } from "@/context/AuthContext";
import { colors } from "@/theme";

type IconName = ComponentProps<typeof MaterialCommunityIcons>["name"];

function icon(name: IconName) {
  return function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return <MaterialCommunityIcons name={name} color={color as string} size={size} />;
  };
}

export default function TabLayout() {
  const { user, loading } = useAuth();
  if (!loading && !user) return <Redirect href="/(auth)/login" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.gold,
        tabBarInactiveTintColor: colors.dim,
        tabBarStyle: {
          backgroundColor: colors.backgroundRaised,
          borderTopColor: colors.borderGold,
          height: 72,
          paddingTop: 7,
          paddingBottom: 8,
        },
        tabBarLabelStyle: { fontSize: 10, fontWeight: "800" },
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
