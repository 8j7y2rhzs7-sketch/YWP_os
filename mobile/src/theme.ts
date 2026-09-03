import type { TextStyle, ViewStyle } from "react-native";

export const colors = {
  background: "#050608",
  backgroundRaised: "#090C11",
  surface: "#0E131A",
  surfaceRaised: "#141B24",
  surfaceGold: "#2B210A",
  gold: "#F5C542",
  goldBright: "#FFE48A",
  goldDark: "#8A6412",
  silver: "#C3C9D3",
  white: "#F8F9FB",
  text: "#F4F6F8",
  muted: "#AEB6C2",
  dim: "#737D8C",
  border: "#2A3442",
  borderGold: "#B88A1C",
  success: "#42E49B",
  successDeep: "#093925",
  warning: "#FFB83E",
  warningDeep: "#3A2807",
  danger: "#FF6577",
  dangerDeep: "#3C1018",
  info: "#50B6FF",
  purple: "#A987FF",
  transparent: "transparent",
} as const;

export const gradients = {
  page: ["#0C1C14", "#12110A", "#1A1208"] as const,
  panel: ["#243028", "#141A1C", "#0C1014"] as const,
  gold: ["#FFE58D", "#E2AD26", "#8B5D08"] as const,
  success: ["#0D3A2A", "#081C16"] as const,
  danger: ["#3A1119", "#170A0D"] as const,
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
  sm: 8,
  md: 14,
  lg: 20,
  pill: 999,
} as const;

export const type = {
  eyebrow: {
    color: colors.gold,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 2.2,
    textTransform: "uppercase",
  } satisfies TextStyle,
  title: {
    color: colors.white,
    fontSize: 30,
    fontWeight: "900",
    letterSpacing: -0.8,
  } satisfies TextStyle,
  section: {
    color: colors.white,
    fontSize: 19,
    fontWeight: "900",
    letterSpacing: 0.2,
  } satisfies TextStyle,
  body: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  } satisfies TextStyle,
  caption: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 17,
  } satisfies TextStyle,
} as const;

export const shadow: ViewStyle = {
  shadowColor: "#000000",
  shadowOffset: { width: 0, height: 8 },
  shadowOpacity: 0.38,
  shadowRadius: 18,
  elevation: 8,
};

export const brand = {
  product: "YWP OS",
  descriptor: "THE UNDERDOG STRATEGIST",
  primaryLine: "DISCIPLINE. DATA. EDGE.",
  secondaryLine: "WE DON'T GUESS, WE ANALYZE.",
  footer: "GRIND EVERYDAY. LONGTERM PAYDAY.",
  protocolVersion: "2026.09.03",
} as const;
