import type { ImageSourcePropType } from "react-native";

/**
 * Canonical YWP visual assets. Keep these imports static so Expo bundles the
 * originals into native and web builds. Reference cards and recovered posters
 * are design standards — never live picks, odds, or verification claims.
 *
 * Vision posters (decision-engine / OS) are dense with baked-in type.
 * Never overlay UI text on top of them — show art alone, or use solid backdrop.
 */
export const brandAssets: Record<string, ImageSourcePropType> = {
  /** Primary mark everywhere — Decision Engine emblem */
  crest: require("../assets/brand/vision/decision-engine-emblem-square.png"),
  minimalLight: require("../assets/brand/ywp-minimal.png"),
  bootSequence: require("../assets/brand/boot-sequence.gif"),
  bootFrame: require("../assets/brand/boot-frame.png"),
  decisionEngine: require("../assets/brand/decision-engine.png"),
  controlBanner: require("../assets/brand/control-banner.png"),
  /** User vision pack — metallic Decision Engine / YWP OS identity */
  decisionEngineEmblem: require("../assets/brand/vision/decision-engine-emblem-square.png"),
  decisionEnginePoster: require("../assets/brand/vision/decision-engine-poster.jpg"),
  ywpOsPoster: require("../assets/brand/vision/ywp-os-poster.jpg"),
  ywpOsControlEmblem: require("../assets/brand/vision/ywp-os-control-emblem.jpg"),
  crownLegacy: require("../assets/brand/ywp-crest.png"),
  mlbProtocolReference: require("../assets/brand/reference-cards/mlb-protocol.png"),
  mlbFinalReference: require("../assets/brand/reference-cards/mlb-final.png"),
  ghosttReference: require("../assets/brand/reference-cards/ghostt.png"),
  sgpPassReference: require("../assets/brand/reference-cards/sgp-pass.png"),
  teamTotalsReference: require("../assets/brand/reference-cards/team-totals.png"),
};
