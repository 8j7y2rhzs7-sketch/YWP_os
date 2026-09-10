import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import {
  Animated,
  RefreshControl,
  StyleSheet,
  View,
  type ViewStyle,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { AmbientField } from "@/components/AmbientField";
import { SignalField } from "@/components/SignalField";
import { sportLook } from "@/sportVisuals";
import { colors, spacing } from "@/theme";

interface ScreenProps {
  children: ReactNode;
  scroll?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
  contentStyle?: ViewStyle;
  sport?: string;
  /** Extra atmospheric sparks behind content. */
  signalField?: boolean;
}

export function Screen({
  children,
  scroll = true,
  refreshing = false,
  onRefresh,
  contentStyle,
  sport,
  signalField = true,
}: ScreenProps) {
  const look = sportLook(sport);
  const enter = useRef(new Animated.Value(0)).current;
  const scrollY = useRef(new Animated.Value(0)).current;
  const insets = useSafeAreaInsets();
  const bottomPad = 86 + Math.max(insets.bottom, 10);

  useEffect(() => {
    Animated.spring(enter, {
      toValue: 1,
      friction: 8,
      tension: 52,
      useNativeDriver: true,
    }).start();
  }, [enter]);

  const parallaxY = scrollY.interpolate({
    inputRange: [0, 220],
    outputRange: [0, -36],
    extrapolate: "clamp",
  });
  const parallaxScale = scrollY.interpolate({
    inputRange: [0, 220],
    outputRange: [1, 1.08],
    extrapolate: "clamp",
  });
  const contentParallax = scrollY.interpolate({
    inputRange: [0, 180],
    outputRange: [0, 8],
    extrapolate: "clamp",
  });

  const content = (
    <Animated.View
      style={[
        styles.content,
        { paddingBottom: bottomPad },
        contentStyle,
        {
          opacity: enter,
          transform: [
            {
              translateY: Animated.add(
                enter.interpolate({
                  inputRange: [0, 1],
                  outputRange: [16, 0],
                }),
                contentParallax,
              ),
            },
          ],
        },
      ]}
    >
      {children}
    </Animated.View>
  );

  return (
    <View style={styles.page}>
      <Animated.View
        pointerEvents="none"
        style={[
          StyleSheet.absoluteFill,
          { transform: [{ translateY: parallaxY }, { scale: parallaxScale }] },
        ]}
      >
        <AmbientField sportAccent={sport ? look.glow : colors.gold} />
        {signalField ? (
          <SignalField
            density="low"
            accent={sport ? look.accent : colors.circuitBlueBright}
            secondary={colors.goldBright}
          />
        ) : null}
      </Animated.View>
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        {scroll ? (
          <Animated.ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
            scrollEventThrottle={16}
            onScroll={Animated.event(
              [{ nativeEvent: { contentOffset: { y: scrollY } } }],
              { useNativeDriver: true },
            )}
            refreshControl={
              onRefresh ? (
                <RefreshControl
                  refreshing={refreshing}
                  onRefresh={onRefresh}
                  tintColor={colors.gold}
                />
              ) : undefined
            }
          >
            {content}
          </Animated.ScrollView>
        ) : (
          content
        )}
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.background },
  safe: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  content: {
    width: "100%",
    maxWidth: 920,
    alignSelf: "center",
    paddingHorizontal: spacing.lg,
    gap: spacing.lg,
  },
});
