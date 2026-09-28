import { StyleSheet, Text, View } from "react-native";

import { EDGE_CHALLENGE_MESSAGE, looksLikeEdgeChallenge } from "@/lib/api";
import { colors, radius, spacing } from "@/theme";

function visibleMessage(message: string | null | undefined): string {
  const trimmed = typeof message === "string" ? message.trim() : "";
  if (!trimmed) {
    return "Something failed, but no details were returned. Tap REFRESH RAW SLATE again. If it keeps happening, sign out and back in (session may be expired).";
  }
  if (looksLikeEdgeChallenge(trimmed)) return EDGE_CHALLENGE_MESSAGE;
  if (trimmed.length > 320) return `${trimmed.slice(0, 319)}…`;
  return trimmed;
}

export function ErrorNotice({ message }: { message: string }) {
  const body = visibleMessage(message);
  return (
    <View style={styles.wrap} accessibilityRole="alert">
      <Text style={styles.title}>CHECK REQUIRED</Text>
      <Text style={styles.message} numberOfLines={8}>
        {body}
      </Text>
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
    gap: spacing.sm,
    minHeight: 72,
  },
  title: {
    color: colors.danger,
    fontWeight: "900",
    letterSpacing: 1,
    fontSize: 13,
  },
  message: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
    fontWeight: "600",
  },
});
