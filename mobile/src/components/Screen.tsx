import type { ReactNode } from "react";
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
  type ViewStyle,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { SafeAreaView } from "react-native-safe-area-context";

import { sportLook } from "@/sportVisuals";
import { colors, gradients, spacing } from "@/theme";

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
  const pageColors = sport
    ? ([look.field, "#12110A", look.field] as const)
    : gradients.page;
  const content = <View style={[styles.content, contentStyle]}>{children}</View>;
  return (
    <LinearGradient colors={pageColors} style={styles.page}>
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
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1 },
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
