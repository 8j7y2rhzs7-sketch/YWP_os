import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import {
  Animated,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AmbientField } from "@/components/AmbientField";
import { sportLook } from "@/sportVisuals";
import { colors, spacing } from "@/theme";

interface ScreenProps {
  children: ReactNode;
  scroll?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
  contentStyle?: ViewStyle;
  sport?: string;
}

export function Screen({
  children,
  scroll = true,
  refreshing = false,
  onRefresh,
  contentStyle,
  sport,
}: ScreenProps) {
  const look = sportLook(sport);
  const enter = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(enter, {
      toValue: 1,
      duration: 420,
      useNativeDriver: true,
    }).start();
  }, [enter]);

  const content = (
    <Animated.View
      style={[
        styles.content,
        contentStyle,
        {
          opacity: enter,
          transform: [
            {
              translateY: enter.interpolate({
                inputRange: [0, 1],
                outputRange: [10, 0],
              }),
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
      <AmbientField sportAccent={sport ? look.glow : colors.gold} />
      <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
        {scroll ? (
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
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
          </ScrollView>
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
    paddingBottom: 120,
    gap: spacing.lg,
  },
});
