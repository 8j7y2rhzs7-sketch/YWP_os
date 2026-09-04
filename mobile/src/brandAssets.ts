import type { ImageSourcePropType } from "react-native";

/**
 * Canonical YWP visual assets. Keep these imports static so Expo bundles the
 * originals into native and web builds. Reference cards and recovered posters
 * are design standards — never live picks, odds, or verification claims.
 */
export const brandAssets: Record<string, ImageSourcePropType> = {
  crest: require("../assets/brand/ywp-crest.png"),
  minimalLight: require("../assets/brand/ywp-minimal.png"),
  bootSequence: require("../assets/brand/boot-sequence.gif"),
  bootFrame: require("../assets/brand/boot-frame.png"),
  decisionEngine: require("../assets/brand/decision-engine.png"),
  controlBanner: require("../assets/brand/control-banner.png"),
  mlbProtocolReference: require("../assets/brand/reference-cards/mlb-protocol.png"),
  mlbFinalReference: require("../assets/brand/reference-cards/mlb-final.png"),
  ghosttReference: require("../assets/brand/reference-cards/ghostt.png"),
  sgpPassReference: require("../assets/brand/reference-cards/sgp-pass.png"),
  teamTotalsReference: require("../assets/brand/reference-cards/team-totals.png"),
};
