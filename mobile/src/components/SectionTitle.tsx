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
    <MotionReveal delay={delay} fromY={8}>
      <View style={styles.copy}>
        <Text style={type.section}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
    </MotionReveal>
  );
}

const styles = StyleSheet.create({
  copy: { gap: 2, paddingTop: spacing.sm },
  subtitle: { ...type.caption, color: colors.muted },
});
