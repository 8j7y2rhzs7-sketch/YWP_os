import { MaterialCommunityIcons } from "@expo/vector-icons";
import { Redirect, Tabs } from "expo-router";
import type { ComponentProps } from "react";
import { Image, Platform, StyleSheet, type ColorValue } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { brandAssets } from "@/brandAssets";
import { useAuth } from "@/context/AuthContext";
import { colors, fonts, radius } from "@/theme";

type IconName = ComponentProps<typeof MaterialCommunityIcons>["name"];

function icon(name: IconName) {
  return function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return <MaterialCommunityIcons name={name} color={color as string} size={size} />;
  };
}

function HomeLogoIcon({ focused }: { color: ColorValue; size: number; focused: boolean }) {
  return (
    <Image
      source={brandAssets.crest}
      style={[styles.homeLogo, focused && styles.homeLogoActive]}
      resizeMode="contain"
      accessibilityLabel="Home"
    />
  );
}

export default function TabLayout() {
  const { user, loading } = useAuth();
  const insets = useSafeAreaInsets();
  // Floating dock: clear of Android system nav, inset from screen edges.
  const bottomInset = Math.max(insets.bottom, 10);
  const tabBarHeight = 58 + bottomInset;

  if (!loading && !user) return <Redirect href="/(auth)/login" />;
  if (!loading && user && !user.has_app_access) return <Redirect href="/(auth)/paywall" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.goldBright,
        tabBarInactiveTintColor: colors.dim,
        tabBarHideOnKeyboard: true,
        tabBarStyle: {
          backgroundColor: "rgba(7,14,22,0.94)",
          borderTopWidth: 0,
          borderWidth: StyleSheet.hairlineWidth,
          borderColor: "rgba(240,193,74,0.28)",
          borderRadius: radius.xl,
          height: tabBarHeight,
          paddingTop: 8,
          paddingBottom: bottomInset,
          position: "absolute",
          left: 12,
          right: 12,
          bottom: 8,
          elevation: 12,
          ...Platform.select({
            ios: {
              shadowColor: "#000",
              shadowOffset: { width: 0, height: 10 },
              shadowOpacity: 0.35,
              shadowRadius: 18,
            },
            default: {},
          }),
        },
        tabBarItemStyle: {
          paddingVertical: 2,
        },
        tabBarLabelStyle: {
          fontSize: 10,
          fontFamily: fonts.bodyBold,
          fontWeight: "700",
          letterSpacing: 0.3,
          marginBottom: 2,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarLabel: "Home",
          tabBarIcon: HomeLogoIcon,
        }}
      />
      <Tabs.Screen
        name="slate"
        options={{ title: "Run", tabBarIcon: icon("chart-timeline-variant-shimmer") }}
      />
      <Tabs.Screen
        name="sheet"
        options={{ title: "Sheet", tabBarIcon: icon("view-grid-plus-outline") }}
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

const styles = StyleSheet.create({
  homeLogo: {
    width: 26,
    height: 26,
    borderRadius: 6,
    opacity: 0.72,
  },
  homeLogoActive: {
    opacity: 1,
    borderWidth: 1,
    borderColor: colors.goldBright,
  },
});
