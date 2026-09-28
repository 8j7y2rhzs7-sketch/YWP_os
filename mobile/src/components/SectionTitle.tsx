import { StyleSheet, Text, View } from "react-native";

import { MotionReveal } from "@/components/MotionReveal";
import { colors, spacing, type } from "@/theme";

export function SectionTitle({
  title,
  subtitle,
  delay = 0,
}: {
  title: string;
  subtitle?: string;
  delay?: number;
}) {
  return (
    <MotionReveal delay={delay} fromY={10}>
      <View style={styles.wrap}>
        <View style={styles.mark}>
          <View style={styles.line} />
          <View style={styles.dot} />
        </View>
        <View style={styles.copy}>
          <Text style={type.section}>{title}</Text>
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        </View>
      </View>
    </MotionReveal>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: "row", alignItems: "stretch", gap: spacing.md },
  mark: { width: 10, alignItems: "center", justifyContent: "center", gap: 5 },
  line: {
    flex: 1,
    width: 2,
    borderRadius: 2,
    backgroundColor: colors.circuitBlue,
    minHeight: 16,
    opacity: 0.9,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.circuitBlueBright,
    shadowColor: colors.circuitBlue,
    shadowOpacity: 0.5,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 0 },
  },
  copy: { flex: 1, gap: 4, paddingVertical: 2 },
  subtitle: { ...type.caption, color: colors.muted },
});
