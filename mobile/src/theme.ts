import type { TextStyle, ViewStyle } from "react-native";

export const fonts = {
  display: "Syne_800ExtraBold",
  displaySemi: "Syne_700Bold",
  body: "DMSans_400Regular",
  bodyMedium: "DMSans_500Medium",
  bodyBold: "DMSans_700Bold",
} as const;

/**
 * Decision Engine identity:
 * black chassis + metallic gold + signature circuit blue from the logo brain.
 *
 * Layout tokens follow 2025–26 consumer-app conventions (DraftKings / Hard Rock /
 * Instagram-class): 8pt grid, 48–56pt controls, tight display tracking, soft cards.
 */
export const colors = {
  background: "#02050A",
  backgroundRaised: "#071018",
  surface: "#0B1520",
  surfaceRaised: "#122030",
  surfaceGold: "#2A1F08",
  surfaceBlue: "#061828",
  gold: "#F0C14A",
  goldBright: "#FFE7A0",
  goldDark: "#8A6412",
  goldMute: "rgba(240,193,74,0.16)",
  /** Signature YWP circuit blue (logo LED / cybernetic half) */
  circuitBlue: "#1AA8F0",
  circuitBlueBright: "#48C4FF",
  circuitBlueDeep: "#0048B0",
  circuitBlueMute: "rgba(26,168,240,0.22)",
  silver: "#D0D6DE",
  white: "#F7F5F0",
  text: "#F1EEE6",
  muted: "#9AA3B0",
  dim: "#6A7484",
  border: "#1E3348",
  borderGold: "#C4982A",
  borderBlue: "rgba(26,168,240,0.45)",
  /** PLAY / win — field green */
  success: "#2EE59A",
  successDeep: "#06281C",
  /** LEAN / caution — jersey amber stripe */
  warning: "#FFB020",
  warningDeep: "#3A2405",
  /** PASS / fail — signal red */
  danger: "#FF4D6A",
  dangerDeep: "#3A0D16",
  info: "#1AA8F0",
  purple: "#A987FF",
  transparent: "transparent",
  ink: "#05070A",
  fieldMist: "rgba(12, 48, 34, 0.55)",
  beam: "rgba(255,255,255,0.08)",
  glass: "rgba(255,255,255,0.045)",
} as const;

export const gradients = {
  page: ["#041018", "#05080C", "#120E06"] as const,
  /** Left circuit blue → night → gold gear warmth (logo split) */
  pageDeep: ["#031526", "#05080C", "#161008"] as const,
  panel: ["#122636", "#0E1822", "#090D12"] as const,
  panelGold: ["#3C2C0A", "#1A160C", "#0A0E12"] as const,
  panelBlue: ["#0A2A44", "#081420", "#090D12"] as const,
  gold: ["#FFE58D", "#E2AD26", "#8B5D08"] as const,
  success: ["#0A3D2C", "#071812"] as const,
  danger: ["#3F121C", "#14080C"] as const,
  ambient: ["rgba(240,193,74,0.2)", "rgba(26,168,240,0.0)"] as const,
  scan: ["rgba(26,168,240,0)", "rgba(26,168,240,0.4)", "rgba(240,193,74,0.35)", "rgba(240,193,74,0)"] as const,
} as const;

/** Strict 8pt grid — matches modern betting / social apps */
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
  huge: 40,
  screen: 20,
  section: 24,
  bottomChrome: 140,
} as const;

export const radius = {
  sm: 12,
  md: 16,
  lg: 20,
  xl: 24,
  pill: 999,
} as const;

/** Minimum interactive height used across buttons / inputs / chips */
export const touch = {
  min: 48,
  comfortable: 56,
} as const;

export const type = {
  /** Small uppercase labels — moderate tracking (not 2018-wide) */
  eyebrow: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.35,
    textTransform: "uppercase",
  } satisfies TextStyle,
  title: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: -1,
    lineHeight: 36,
  } satisfies TextStyle,
  section: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 19,
    fontWeight: "700",
    letterSpacing: -0.35,
    lineHeight: 24,
  } satisfies TextStyle,
  body: {
    color: colors.text,
    fontFamily: fonts.body,
    fontSize: 16,
    lineHeight: 24,
    letterSpacing: -0.1,
  } satisfies TextStyle,
  caption: {
    color: colors.muted,
    fontFamily: fonts.bodyMedium,
    fontSize: 13,
    lineHeight: 18,
    letterSpacing: 0.1,
  } satisfies TextStyle,
  button: {
    fontFamily: fonts.displaySemi,
    fontSize: 15,
    fontWeight: "700",
    letterSpacing: 0.4,
  } satisfies TextStyle,
  label: {
    color: colors.silver,
    fontFamily: fonts.bodyBold,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.9,
    textTransform: "uppercase",
  } satisfies TextStyle,
} as const;

/** Soft elevation — modern apps avoid heavy drop shadows */
export const shadow: ViewStyle = {
  shadowColor: "#000000",
  shadowOffset: { width: 0, height: 8 },
  shadowOpacity: 0.28,
  shadowRadius: 16,
  elevation: 6,
};

export const brand = {
  product: "YWP OS",
  descriptor: "THE UNDERDOG STRATEGIST",
  primaryLine: "DISCIPLINE. DATA. EDGE.",
  secondaryLine: "WE DON'T GUESS, WE ANALYZE.",
  footer: "GRIND EVERYDAY. LONGTERM PAYDAY.",
  tagline: "YOUR WINNING PROCESS",
  protocolVersion: "2026.09.03",
  skin: "DECISION ENGINE",
} as const;
