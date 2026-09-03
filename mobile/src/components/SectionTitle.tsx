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
      <View style={styles.line} />
      <View style={styles.copy}>
        <Text style={type.section}>{title}</Text>
        {subtitle ? <Text style={type.caption}>{subtitle}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: "row", alignItems: "stretch", gap: spacing.md },
  line: { width: 3, borderRadius: 2, backgroundColor: colors.gold },
  copy: { flex: 1, gap: 2 },
});
