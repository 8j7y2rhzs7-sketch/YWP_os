import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "@/theme";

export function LoadingState({ label = "Running YWP protocol…" }: { label?: string }) {
  return (
    <View style={styles.wrap}>
      <ActivityIndicator size="large" color={colors.gold} />
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { padding: spacing.huge, alignItems: "center", gap: spacing.md },
  label: { color: colors.muted, fontWeight: "700" },
});
