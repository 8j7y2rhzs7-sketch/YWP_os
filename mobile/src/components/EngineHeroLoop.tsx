import { useEffect } from "react";
import {
  Image,
  Platform,
  StyleSheet,
  View,
  type ImageSourcePropType,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { VideoView, useVideoPlayer } from "expo-video";

import { brandAssets } from "@/brandAssets";
import { useReduceMotion } from "@/hooks/useReduceMotion";
import { colors } from "@/theme";

interface EngineHeroLoopProps {
  size?: number;
  /** Circular crop for orbit core; rectangular for full stage backdrop. */
  shape?: "circle" | "rounded" | "rect";
  style?: StyleProp<ViewStyle>;
  sourceVideo?: number;
  sourceGif?: ImageSourcePropType;
  sourceStill?: ImageSourcePropType;
}

/**
 * Production path for reel-grade motion: a real looping render (mp4)
 * sits under/inside the Decision Engine chrome.
 *
 * Swap `assets/brand/vision/decision-engine-loop.mp4` to upgrade art
 * without code changes. Falls back to boot GIF, then static emblem.
 */
export function EngineHeroLoop({
  size = 180,
  shape = "circle",
  style,
  sourceVideo = brandAssets.decisionEngineLoop,
  sourceGif = brandAssets.bootSequence,
  sourceStill = brandAssets.decisionEngineEmblem,
}: EngineHeroLoopProps) {
  const reduceMotion = useReduceMotion();
  const radius =
    shape === "circle" ? size / 2 : shape === "rounded" ? Math.min(28, size * 0.12) : 0;

  const player = useVideoPlayer(sourceVideo, (next) => {
    next.loop = true;
    next.muted = true;
    next.playbackRate = 1;
    next.play();
  });

  useEffect(() => {
    if (reduceMotion) {
      try {
        player.pause();
      } catch {
        /* ignore */
      }
      return;
    }
    try {
      player.loop = true;
      player.muted = true;
      player.play();
    } catch {
      /* ignore */
    }
  }, [player, reduceMotion]);

  // Web / reduce-motion: animated GIF or still — no native video surface required.
  if (reduceMotion || Platform.OS === "web") {
    return (
      <View
        style={[
          styles.wrap,
          { width: size, height: size, borderRadius: radius },
          style,
        ]}
      >
        <Image
          source={reduceMotion ? sourceStill : sourceGif}
          style={styles.media}
          resizeMode="cover"
          accessibilityLabel="YWP Decision Engine motion"
        />
        <View pointerEvents="none" style={styles.vignette} />
      </View>
    );
  }

  return (
    <View
      style={[
        styles.wrap,
        { width: size, height: size, borderRadius: radius },
        style,
      ]}
    >
      <VideoView
        player={player}
        style={styles.media}
        contentFit="cover"
        nativeControls={false}
        playsInline
      />
      <View pointerEvents="none" style={styles.vignette} />
      <View pointerEvents="none" style={styles.edge} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    overflow: "hidden",
    backgroundColor: colors.background,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(240,193,74,0.35)",
  },
  media: {
    width: "100%",
    height: "100%",
  },
  vignette: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(2,5,10,0.18)",
  },
  edge: {
    ...StyleSheet.absoluteFill,
    borderWidth: 1,
    borderColor: "rgba(26,168,240,0.28)",
  },
});
