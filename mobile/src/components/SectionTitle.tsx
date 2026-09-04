import { StyleSheet, Text, View } from "react-native";

import { colors, spacing, type } from "@/theme";

export function SectionTitle({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <View style={styles.wrap}>
      <View style={styles.mark}>
        <View style={styles.line} />
        <View style={styles.dot} />
      </View>
      <View style={styles.copy}>
        <Text style={type.section}>{title}</Text>
        {subtitle ? <Text style={type.caption}>{subtitle}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: "row", alignItems: "stretch", gap: spacing.md },
  mark: { width: 10, alignItems: "center", justifyContent: "center", gap: 4 },
  line: {
    flex: 1,
    width: 2,
    borderRadius: 2,
    backgroundColor: colors.gold,
    minHeight: 18,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.goldBright,
  },
  copy: { flex: 1, gap: 3 },
});
