import type { ImageSourcePropType } from "react-native";

/**
 * Canonical YWP visual assets. Keep these imports static so Expo bundles the
 * originals into native and web builds. Reference cards and recovered posters
 * are design standards — never live picks, odds, or verification claims.
 *
 * Vision posters (decision-engine / OS) are dense with baked-in type.
 * Never overlay UI text on top of them — show art alone, or use solid backdrop.
 *
 * Motion: decisionEngineLoop is the looping hero render used by EngineHeroLoop.
 * Drop a replacement mp4 at the same path to upgrade the art without code changes.
 */
export const brandAssets = {
  /** Primary mark everywhere — Decision Engine emblem */
  crest: require("../assets/brand/vision/decision-engine-emblem-square.png"),
  minimalLight: require("../assets/brand/ywp-minimal.png"),
  bootSequence: require("../assets/brand/boot-sequence.gif"),
  bootFrame: require("../assets/brand/boot-frame.png"),
  decisionEngine: require("../assets/brand/decision-engine.png"),
  controlBanner: require("../assets/brand/control-banner.png"),
  /** Looping Decision Engine hero render (mp4) */
  decisionEngineLoop: require("../assets/brand/vision/decision-engine-loop.mp4"),
  /** User vision pack — metallic Decision Engine / YWP OS identity */
  decisionEngineEmblem: require("../assets/brand/vision/decision-engine-emblem-square.png"),
  decisionEnginePoster: require("../assets/brand/vision/decision-engine-poster.jpg"),
  ywpOsPoster: require("../assets/brand/vision/ywp-os-poster.jpg"),
  ywpOsControlEmblem: require("../assets/brand/vision/ywp-os-control-emblem.jpg"),
  crownLegacy: require("../assets/brand/ywp-crest.png"),
  /** Tab dock emblems — same metallic crest language as the logo */
  tabRun: require("../assets/brand/tabs/run.png"),
  tabSheet: require("../assets/brand/tabs/sheet.png"),
  tabTickets: require("../assets/brand/tabs/tickets.png"),
  tabLearning: require("../assets/brand/tabs/learning.png"),
  tabControls: require("../assets/brand/tabs/controls.png"),
  mlbProtocolReference: require("../assets/brand/reference-cards/mlb-protocol.png"),
  mlbFinalReference: require("../assets/brand/reference-cards/mlb-final.png"),
  ghosttReference: require("../assets/brand/reference-cards/ghostt.png"),
  sgpPassReference: require("../assets/brand/reference-cards/sgp-pass.png"),
  teamTotalsReference: require("../assets/brand/reference-cards/team-totals.png"),
} as const satisfies Record<string, number>;

export type BrandAssetKey = keyof typeof brandAssets;
export type BrandImageSource = ImageSourcePropType;
