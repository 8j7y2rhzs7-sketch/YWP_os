import NetInfo from "@react-native-community/netinfo";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "../theme";

export function OfflineNotice() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      setOffline(state.isConnected === false);
    });
    return () => unsubscribe();
  }, []);

  if (!offline) return null;

  return (
    <View style={styles.bar} accessibilityRole="alert">
      <Text style={styles.text}>No internet connection. Data may be stale.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.warningDeep,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    alignItems: "center",
  },
  text: {
    color: colors.warning,
    fontWeight: "800",
    fontSize: 12,
    letterSpacing: 0.5,
  },
});
