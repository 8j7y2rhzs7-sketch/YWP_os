import type { TextStyle, ViewStyle } from "react-native";

export const fonts = {
  display: "Syne_800ExtraBold",
  displaySemi: "Syne_700Bold",
  body: "DMSans_400Regular",
  bodyMedium: "DMSans_500Medium",
  bodyBold: "DMSans_700Bold",
} as const;

export const colors = {
  background: "#040506",
  backgroundRaised: "#0A0D12",
  surface: "#10151C",
  surfaceRaised: "#171E28",
  surfaceGold: "#2B210A",
  gold: "#F0C14A",
  goldBright: "#FFE7A0",
  goldDark: "#8A6412",
  goldMute: "rgba(240,193,74,0.14)",
  silver: "#C7CDD6",
  white: "#F7F5F0",
  text: "#F1EEE6",
  muted: "#9AA3B0",
  dim: "#6A7484",
  border: "#2A3340",
  borderGold: "#C4982A",
  success: "#3FDB96",
  successDeep: "#093925",
  warning: "#FFB83E",
  warningDeep: "#3A2807",
  danger: "#FF6577",
  dangerDeep: "#3C1018",
  info: "#50B6FF",
  purple: "#A987FF",
  transparent: "transparent",
  ink: "#07090C",
  fieldMist: "rgba(15, 40, 28, 0.55)",
} as const;

export const gradients = {
  page: ["#07140F", "#0B0C0A", "#161008"] as const,
  pageDeep: ["#050807", "#0A0C0B", "#120E08"] as const,
  panel: ["#1C2822", "#12181C", "#0B0F14"] as const,
  panelGold: ["#3A2C0C", "#1A150A", "#0A0C10"] as const,
  gold: ["#FFE58D", "#E2AD26", "#8B5D08"] as const,
  success: ["#0D3A2A", "#081C16"] as const,
  danger: ["#3A1119", "#170A0D"] as const,
  ambient: ["rgba(240,193,74,0.18)", "rgba(240,193,74,0.0)"] as const,
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  huge: 48,
} as const;

export const radius = {
  sm: 10,
  md: 16,
  lg: 22,
  pill: 999,
} as const;

export const type = {
  eyebrow: {
    color: colors.gold,
    fontFamily: fonts.bodyBold,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 2.4,
    textTransform: "uppercase",
  } satisfies TextStyle,
  title: {
    color: colors.white,
    fontFamily: fonts.display,
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: -0.6,
  } satisfies TextStyle,
  section: {
    color: colors.white,
    fontFamily: fonts.displaySemi,
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: 0.1,
  } satisfies TextStyle,
  body: {
    color: colors.text,
    fontFamily: fonts.body,
    fontSize: 15,
    lineHeight: 23,
  } satisfies TextStyle,
  caption: {
    color: colors.muted,
    fontFamily: fonts.bodyMedium,
    fontSize: 12,
    lineHeight: 17,
  } satisfies TextStyle,
} as const;

export const shadow: ViewStyle = {
  shadowColor: "#000000",
  shadowOffset: { width: 0, height: 10 },
  shadowOpacity: 0.42,
  shadowRadius: 22,
  elevation: 10,
};

export const brand = {
  product: "YWP OS",
  descriptor: "THE UNDERDOG STRATEGIST",
  primaryLine: "DISCIPLINE. DATA. EDGE.",
  secondaryLine: "WE DON'T GUESS, WE ANALYZE.",
  footer: "GRIND EVERYDAY. LONGTERM PAYDAY.",
  protocolVersion: "2026.09.03",
} as const;
