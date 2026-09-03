import { StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "@/theme";

export function ErrorNotice({ message }: { message: string }) {
  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>CHECK REQUIRED</Text>
      <Text style={styles.message}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderWidth: 1,
    borderColor: colors.danger,
    backgroundColor: colors.dangerDeep,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.xs,
  },
  title: { color: colors.danger, fontWeight: "900", letterSpacing: 1 },
  message: { color: colors.white, fontSize: 13, lineHeight: 19 },
});
