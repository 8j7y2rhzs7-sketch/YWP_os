import { StyleSheet, Text, TextInput, type TextInputProps } from "react-native";

import { colors, fonts, radius, spacing, touch, type , registerStyles } from "@/theme";

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
        selectionColor={colors.circuitBlueBright}
        style={[styles.input, props.multiline && styles.multiline, props.style]}
      />
    </>
  );
}

const styles = registerStyles(() => StyleSheet.create({
  label: {
    ...type.label,
    marginBottom: 2,
  },
  input: {
    minHeight: touch.comfortable,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.inputBorder,
    backgroundColor: colors.input,
    color: colors.white,
    fontFamily: fonts.body,
    fontSize: 16,
    letterSpacing: -0.1,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  multiline: { minHeight: 112, textAlignVertical: "top", paddingTop: spacing.lg },
}));
