import { Image, StyleSheet, Text, View } from "react-native";

import { sportLook } from "@/sportVisuals";
import { colors, radius } from "@/theme";

export function PlayerPortrait({
  imageUrl,
  teamImageUrl,
  sport,
  size = 52,
}: {
  imageUrl?: string | null;
  teamImageUrl?: string | null;
  sport?: string;
  size?: number;
}) {
  const look = sportLook(sport);
  const src = imageUrl || teamImageUrl;
  return (
    <View
      style={[
        styles.wrap,
        { width: size, height: size, borderRadius: size / 2, backgroundColor: look.field },
      ]}
    >
      {src ? (
        <Image source={{ uri: src }} style={styles.image} />
      ) : (
        <Text style={[styles.emoji, { fontSize: size * 0.42 }]}>{look.emoji}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.borderGold,
  },
  image: { width: "100%", height: "100%" },
  emoji: { color: colors.gold },
});
