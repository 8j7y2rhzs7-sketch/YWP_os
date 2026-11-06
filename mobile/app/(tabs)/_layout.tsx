import { Ionicons } from "@expo/vector-icons";
import { Redirect, Tabs } from "expo-router";
import type { ComponentProps } from "react";
import { Platform, StyleSheet, View, type ColorValue } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/context/AuthContext";
import { colors, fonts, radius } from "@/theme";

type IonName = ComponentProps<typeof Ionicons>["name"];

const tabIcons = {
  index: { idle: "home-outline", active: "home" },
  slate: { idle: "play-outline", active: "play" },
  sheet: { idle: "grid-outline", active: "grid" },
  tickets: { idle: "layers-outline", active: "layers" },
  learning: { idle: "school-outline", active: "school" },
  markets: { idle: "stats-chart-outline", active: "stats-chart" },
  settings: { idle: "options-outline", active: "options" },
} as const satisfies Record<string, { idle: IonName; active: IonName }>;

function TabGlyph({
  route,
  focused,
}: {
  route: keyof typeof tabIcons;
  color: ColorValue;
  size: number;
  focused: boolean;
}) {
  const icon = tabIcons[route];
  return (
    <View style={[styles.glyph, focused && styles.glyphOn]}>
      <Ionicons
        name={focused ? icon.active : icon.idle}
        size={18}
        color={focused ? colors.ink : colors.muted}
      />
    </View>
  );
}

function tabIcon(route: keyof typeof tabIcons) {
  return function Icon(props: { color: ColorValue; size: number; focused: boolean }) {
    return <TabGlyph {...props} route={route} />;
  };
}

export default function TabLayout() {
  const { user, loading } = useAuth();
  const insets = useSafeAreaInsets();
  const bottomInset = Math.max(insets.bottom, 8);
  const tabBarHeight = 62 + bottomInset;

  if (!loading && !user) return <Redirect href="/(auth)/login" />;
  if (!loading && user && !user.has_app_access) return <Redirect href="/(auth)/paywall" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.goldBright,
        tabBarInactiveTintColor: colors.muted,
        tabBarHideOnKeyboard: true,
        tabBarStyle: {
          backgroundColor: "rgba(8,12,18,0.96)",
          borderTopWidth: 0,
          borderWidth: StyleSheet.hairlineWidth,
          borderColor: "rgba(255,255,255,0.1)",
          borderRadius: radius.xl,
          height: tabBarHeight,
          paddingTop: 6,
          paddingBottom: bottomInset,
          position: "absolute",
          left: 10,
          right: 10,
          bottom: 8,
          elevation: 16,
          ...Platform.select({
            ios: {
              shadowColor: "#000",
              shadowOffset: { width: 0, height: 12 },
              shadowOpacity: 0.4,
              shadowRadius: 20,
            },
            default: {},
          }),
        },
        tabBarItemStyle: {
          paddingVertical: 0,
        },
        tabBarLabelStyle: {
          fontSize: 9,
          fontFamily: fonts.bodyBold,
          fontWeight: "700",
          letterSpacing: 0,
          marginTop: 2,
          marginBottom: 0,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: "Home", tabBarLabel: "Home", tabBarIcon: tabIcon("index") }}
      />
      <Tabs.Screen
        name="slate"
        options={{ title: "Run", tabBarLabel: "Run", tabBarIcon: tabIcon("slate") }}
      />
      <Tabs.Screen
        name="sheet"
        options={{ title: "Sheet", tabBarLabel: "Sheet", tabBarIcon: tabIcon("sheet") }}
      />
      <Tabs.Screen
        name="tickets"
        options={{ title: "Tickets", tabBarLabel: "Tickets", tabBarIcon: tabIcon("tickets") }}
      />
      <Tabs.Screen
        name="learning"
        options={{ title: "Learn", tabBarLabel: "Learn", tabBarIcon: tabIcon("learning") }}
      />
      <Tabs.Screen
        name="markets"
        options={{ title: "Markets", tabBarLabel: "Markets", tabBarIcon: tabIcon("markets") }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: "More", tabBarLabel: "More", tabBarIcon: tabIcon("settings") }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  glyph: {
    width: 32,
    height: 24,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  glyphOn: {
    backgroundColor: colors.gold,
  },
});
