import type { ImageSourcePropType } from "react-native";

/**
 * Canonical YWP visual assets. Keep these imports static so Expo bundles the
 * originals into native and web builds. Reference cards are design standards,
 * not sample picks and never become live recommendation data.
 */
export const brandAssets: Record<string, ImageSourcePropType> = {
  crest: require("../assets/brand/ywp-crest.png"),
  minimalLight: require("../assets/brand/ywp-minimal.png"),
  mlbProtocolReference: require("../assets/brand/reference-cards/mlb-protocol.png"),
  mlbFinalReference: require("../assets/brand/reference-cards/mlb-final.png"),
  ghosttReference: require("../assets/brand/reference-cards/ghostt.png"),
  sgpPassReference: require("../assets/brand/reference-cards/sgp-pass.png"),
  teamTotalsReference: require("../assets/brand/reference-cards/team-totals.png"),
};
