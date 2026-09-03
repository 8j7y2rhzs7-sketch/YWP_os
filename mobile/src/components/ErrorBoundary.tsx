import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { submitErrorReport } from "../lib/errorReporting";
import { colors, spacing, type } from "../theme";
import { YwpButton } from "./YwpButton";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  reported: boolean;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, reported: false };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    if (this.state.reported) return;
    this.setState({ reported: true });
    void submitErrorReport({
      category: "crash",
      message: error.message || "Unhandled UI crash",
      screen: "ErrorBoundary",
      stack: `${error.stack ?? ""}\n${info.componentStack ?? ""}`.slice(0, 11000),
      context: { name: error.name },
    }).catch(() => {
      // Never block recovery on reporting failure.
    });
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null, reported: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <View style={styles.container}>
          <Text style={styles.icon}>⚠</Text>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.message}>
            {this.state.error?.message || "An unexpected error occurred."}
          </Text>
          <Text style={styles.caption}>
            A crash report was sent so we can fix this after you keep using the app.
          </Text>
          <YwpButton label="Try again" onPress={this.handleReset} style={styles.btn} />
        </View>
      );
    }
    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  icon: {
    fontSize: 48,
    marginBottom: spacing.md,
  },
  title: {
    ...type.section,
    color: colors.goldBright,
    marginBottom: spacing.sm,
    textAlign: "center",
  },
  message: {
    ...type.body,
    color: colors.muted,
    textAlign: "center",
    marginBottom: spacing.md,
    maxWidth: 320,
  },
  caption: {
    ...type.caption,
    textAlign: "center",
    marginBottom: spacing.lg,
    maxWidth: 320,
  },
  btn: {
    minWidth: 160,
  },
});
