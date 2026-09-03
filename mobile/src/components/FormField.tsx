import { StyleSheet, Text, TextInput, type TextInputProps } from "react-native";

import { colors, radius, spacing } from "@/theme";

export function FormField({
  label,
  ...props
}: TextInputProps & { label: string }) {
  return (
    <>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        {...props}
        placeholderTextColor={colors.dim}
        selectionColor={colors.gold}
        style={[styles.input, props.multiline && styles.multiline, props.style]}
      />
    </>
  );
}

const styles = StyleSheet.create({
  label: {
    color: colors.silver,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  input: {
    minHeight: 50,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.backgroundRaised,
    color: colors.white,
    fontSize: 15,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  multiline: { minHeight: 100, textAlignVertical: "top" },
});
