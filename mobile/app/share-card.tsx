import * as Sharing from "expo-sharing";
import { router, useLocalSearchParams } from "expo-router";
import { useRef, useState } from "react";
import {
  Alert,
  PixelRatio,
  Platform,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { captureRef } from "react-native-view-shot";

import { ErrorNotice } from "@/components/ErrorNotice";
import { Screen } from "@/components/Screen";
import { ShareCard } from "@/components/ShareCard";
import { YwpButton } from "@/components/YwpButton";
import { useAppData } from "@/context/AppDataContext";
import { colors, spacing, type } from "@/theme";

export default function ShareCardScreen() {
  const params = useLocalSearchParams<{ analysisId: string; cardKey: string }>();
  const analysisId = Array.isArray(params.analysisId)
    ? params.analysisId[0]
    : params.analysisId;
  const cardKey = Array.isArray(params.cardKey) ? params.cardKey[0] : params.cardKey;
  const { analyses, builds } = useAppData();
  const analysis = analysisId ? analyses[analysisId] : undefined;
  const card = analysisId && cardKey ? builds[analysisId]?.cards[cardKey] : undefined;
  const cardRef = useRef<View>(null);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function exportCard() {
    if (!cardRef.current || !card) return;
    setExporting(true);
    setError(null);
    try {
      const pixelRatio = PixelRatio.get();
      if (Platform.OS === "web") {
        const dataUri = await captureRef(cardRef.current, {
          format: "png",
          quality: 1,
          result: "data-uri",
          width: 1080 / pixelRatio,
          height: 1350 / pixelRatio,
        });
        const anchor = document.createElement("a");
        anchor.download = `YWP_OS_${card.key}.png`;
        anchor.href = dataUri;
        anchor.click();
      } else {
        const uri = await captureRef(cardRef.current, {
          format: "png",
          quality: 1,
          result: "tmpfile",
          width: 1080 / pixelRatio,
          height: 1350 / pixelRatio,
        });
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(uri, {
            mimeType: "image/png",
            dialogTitle: `Share ${card.label}`,
            UTI: "public.png",
          });
        } else {
          Alert.alert("Graphic created", uri);
        }
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Graphic could not be exported");
    } finally {
      setExporting(false);
    }
  }

  if (!analysis || !card) {
    return (
      <Screen>
        <ErrorNotice message="The selected card is no longer in memory. Return to the Decision Board and open its graphic again." />
        <YwpButton label="BACK TO PROTOCOL RUN" onPress={() => router.replace("/(tabs)/slate")} />
      </Screen>
    );
  }

  return (
    <Screen>
      <Text style={styles.title}>YWP GRAPHIC STUDIO</Text>
      <Text style={type.caption}>
        The live component below is the production template. Export generates a
        1080 × 1350 PNG using the same brand tokens and original crest bundled in
        source.
      </Text>
      {error ? <ErrorNotice message={error} /> : null}
      <View style={styles.preview}>
        <ShareCard
          ref={cardRef}
          card={card}
          slateDate={analysis.date}
          sport={card.legs[0]?.sport ?? "multi"}
        />
      </View>
      <YwpButton label="EXPORT / SHARE 1080 × 1350 PNG" onPress={() => void exportCard()} loading={exporting} />
      <YwpButton label="BACK TO DECISION BOARD" variant="outline" onPress={() => router.back()} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: { color: colors.gold, fontSize: 24, fontWeight: "900", paddingTop: spacing.md },
  preview: {
    width: "100%",
    maxWidth: 720,
    alignSelf: "center",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 14 },
    shadowOpacity: 0.55,
    shadowRadius: 25,
    elevation: 12,
  },
});
