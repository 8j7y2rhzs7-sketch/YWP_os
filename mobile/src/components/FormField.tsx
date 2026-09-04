import { StyleSheet, Text, TextInput, type TextInputProps } from "react-native";

import { colors, fonts, radius, spacing } from "@/theme";

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
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.0,
    textTransform: "uppercase",
  },
  input: {
    minHeight: 52,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: "rgba(196,152,42,0.28)",
    backgroundColor: "rgba(10,13,18,0.88)",
    color: colors.white,
    fontFamily: fonts.body,
    fontSize: 15,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  multiline: { minHeight: 100, textAlignVertical: "top" },
});
