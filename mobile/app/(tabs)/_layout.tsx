import { Redirect, Tabs } from "expo-router";
import { Image, Platform, StyleSheet, type ColorValue, type ImageSourcePropType } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { brandAssets } from "@/brandAssets";
import { useAuth } from "@/context/AuthContext";
import { colors, fonts, radius } from "@/theme";

function BrandTabIcon({
  source,
  label,
  focused,
}: {
  source: ImageSourcePropType;
  label: string;
  color: ColorValue;
  size: number;
  focused: boolean;
}) {
  return (
    <Image
      source={source}
      style={[styles.tabEmblem, focused && styles.tabEmblemActive]}
      resizeMode="contain"
      accessibilityLabel={label}
    />
  );
}

function tabIcon(source: ImageSourcePropType, label: string) {
  return function TabEmblemIcon(props: { color: ColorValue; size: number; focused: boolean }) {
    return <BrandTabIcon {...props} source={source} label={label} />;
  };
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
          tabBarIcon: tabIcon(brandAssets.crest, "Home"),
        }}
      />
      <Tabs.Screen
        name="slate"
        options={{ title: "Run", tabBarIcon: tabIcon(brandAssets.tabRun, "Run") }}
      />
      <Tabs.Screen
        name="sheet"
        options={{ title: "Sheet", tabBarIcon: tabIcon(brandAssets.tabSheet, "Sheet") }}
      />
      <Tabs.Screen
        name="tickets"
        options={{ title: "Tickets", tabBarIcon: tabIcon(brandAssets.tabTickets, "Tickets") }}
      />
      <Tabs.Screen
        name="learning"
        options={{ title: "Learning", tabBarIcon: tabIcon(brandAssets.tabLearning, "Learning") }}
      />
      <Tabs.Screen
        name="settings"
        options={{ title: "Controls", tabBarIcon: tabIcon(brandAssets.tabControls, "Controls") }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabEmblem: {
    width: 28,
    height: 28,
    opacity: 0.7,
  },
  tabEmblemActive: {
    opacity: 1,
  },
});
