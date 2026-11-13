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
 * Light mode is ice white with a cyan-to-gold flare: electric circuit blue,
 * saturated gold on buttons and edges, ink text so it still reads.
 */
export type Palette = {
  background: string;
  backgroundRaised: string;
  surface: string;
  surfaceRaised: string;
  surfaceGold: string;
  surfaceBlue: string;
  gold: string;
  goldBright: string;
  goldDark: string;
  goldMute: string;
  circuitBlue: string;
  circuitBlueBright: string;
  circuitBlueDeep: string;
  circuitBlueMute: string;
  silver: string;
  white: string;
  text: string;
  muted: string;
  dim: string;
  border: string;
  borderGold: string;
  borderBlue: string;
  success: string;
  successDeep: string;
  warning: string;
  warningDeep: string;
  danger: string;
  dangerDeep: string;
  info: string;
  purple: string;
  transparent: string;
  ink: string;
  fieldMist: string;
  beam: string;
  glass: string;
  dock: string;
  input: string;
  inputBorder: string;
  grain: string;
  panelLine: string;
};

export type GradientSet = {
  page: readonly [string, string, string];
  pageDeep: readonly [string, string, string];
  panel: readonly [string, string, string];
  panelGold: readonly [string, string, string];
  panelBlue: readonly [string, string, string];
  gold: readonly [string, string, string];
  success: readonly [string, string];
  danger: readonly [string, string];
  outline: readonly [string, string];
  ambient: readonly [string, string];
  scan: readonly [string, string, string, string];
  vignette: readonly [string, string, string];
};

const darkColors: Palette = {
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
  success: "#2EE59A",
  successDeep: "#06281C",
  warning: "#FFB020",
  warningDeep: "#3A2405",
  danger: "#FF4D6A",
  dangerDeep: "#3A0D16",
  info: "#1AA8F0",
  purple: "#A987FF",
  transparent: "transparent",
  ink: "#05070A",
  fieldMist: "rgba(12, 48, 34, 0.55)",
  beam: "rgba(255,255,255,0.08)",
  glass: "rgba(255,255,255,0.045)",
  dock: "rgba(7,14,22,0.94)",
  input: "rgba(8,14,22,0.92)",
  inputBorder: "rgba(26,168,240,0.28)",
  grain: "rgba(255,255,255,0.014)",
  panelLine: "rgba(255,255,255,0.12)",
};

const lightColors: Palette = {
  background: "#F4FBFF",
  backgroundRaised: "#FFFFFF",
  surface: "#FFFFFF",
  surfaceRaised: "#E4F7FF",
  surfaceGold: "#FFE08A",
  surfaceBlue: "#CFF3FF",
  gold: "#C45F00",
  goldBright: "#FFB000",
  goldDark: "#8A3E00",
  goldMute: "rgba(255,176,0,0.28)",
  circuitBlue: "#0077E6",
  circuitBlueBright: "#00B4FF",
  circuitBlueDeep: "#0057C2",
  circuitBlueMute: "rgba(0,180,255,0.24)",
  silver: "#1C3148",
  white: "#071422",
  text: "#10263C",
  muted: "#3A5674",
  dim: "#5A7694",
  border: "#9FE3FF",
  borderGold: "#FFB000",
  borderBlue: "rgba(0,180,255,0.72)",
  success: "#00C26A",
  successDeep: "#D6FFEE",
  warning: "#FF7A00",
  warningDeep: "#FFF0D8",
  danger: "#FF2D6A",
  dangerDeep: "#FFE3EE",
  info: "#0077E6",
  purple: "#6D4DFF",
  transparent: "transparent",
  ink: "#071422",
  fieldMist: "rgba(0,194,106,0.18)",
  beam: "rgba(0,180,255,0.20)",
  glass: "rgba(0,180,255,0.10)",
  dock: "rgba(255,255,255,0.94)",
  input: "#FFFFFF",
  inputBorder: "rgba(0,180,255,0.62)",
  grain: "rgba(0,180,255,0.05)",
  panelLine: "rgba(0,180,255,0.42)",
};

const darkGradients: GradientSet = {
  page: ["#041018", "#05080C", "#120E06"],
  pageDeep: ["#031526", "#05080C", "#161008"],
  panel: ["#122636", "#0E1822", "#090D12"],
  panelGold: ["#3C2C0A", "#1A160C", "#0A0E12"],
  panelBlue: ["#0A2A44", "#081420", "#090D12"],
  gold: ["#FFE58D", "#E2AD26", "#8B5D08"],
  success: ["#0A3D2C", "#071812"],
  danger: ["#3F121C", "#14080C"],
  outline: ["#151B23", "#0A0D12"],
  ambient: ["rgba(240,193,74,0.2)", "rgba(26,168,240,0.0)"],
  scan: ["rgba(26,168,240,0)", "rgba(26,168,240,0.4)", "rgba(240,193,74,0.35)", "rgba(240,193,74,0)"],
  vignette: ["transparent", "rgba(2,5,10,0.42)", "rgba(2,5,10,0.94)"],
};

const lightGradients: GradientSet = {
  page: ["#D9F6FF", "#FFFFFF", "#FFF3C4"],
  pageDeep: ["#B6ECFF", "#F5FCFF", "#FFE07A"],
  panel: ["#FFFFFF", "#F2FBFF", "#FFF8DE"],
  panelGold: ["#FFE36A", "#FFF4C2", "#FFFFFF"],
  panelBlue: ["#A8E8FF", "#E7F8FF", "#FFFFFF"],
  gold: ["#FFE566", "#FFC400", "#FF9A00"],
  success: ["#B8FFDF", "#F2FFF8"],
  danger: ["#FFC6DA", "#FFF4F8"],
  outline: ["#FFFFFF", "#E5F7FF"],
  ambient: ["rgba(255,196,0,0.55)", "rgba(0,180,255,0)"],
  scan: ["rgba(0,180,255,0)", "rgba(0,180,255,0.62)", "rgba(255,196,0,0.55)", "rgba(255,196,0,0)"],
  vignette: ["transparent", "rgba(255,255,255,0)", "rgba(182,236,255,0.28)"],
};

function buildType(c: Palette) {
  return {
    eyebrow: {
      color: c.gold,
      fontFamily: fonts.bodyBold,
      fontSize: 11,
      fontWeight: "700",
      letterSpacing: 1.35,
      textTransform: "uppercase",
    } satisfies TextStyle,
    title: {
      color: c.white,
      fontFamily: fonts.display,
      fontSize: 32,
      fontWeight: "800",
      letterSpacing: -1,
      lineHeight: 36,
    } satisfies TextStyle,
    section: {
      color: c.white,
      fontFamily: fonts.displaySemi,
      fontSize: 19,
      fontWeight: "700",
      letterSpacing: -0.35,
      lineHeight: 24,
    } satisfies TextStyle,
    body: {
      color: c.text,
      fontFamily: fonts.body,
      fontSize: 16,
      lineHeight: 24,
      letterSpacing: -0.1,
    } satisfies TextStyle,
    caption: {
      color: c.muted,
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
      color: c.silver,
      fontFamily: fonts.bodyBold,
      fontSize: 12,
      fontWeight: "700",
      letterSpacing: 0.9,
      textTransform: "uppercase",
    } satisfies TextStyle,
  };
}

export type TypeScale = ReturnType<typeof buildType>;
export type ColorSchemeName = "light" | "dark";

type ActiveTheme = {
  scheme: ColorSchemeName;
  colors: Palette;
  gradients: GradientSet;
  type: TypeScale;
};

let active: ActiveTheme = {
  scheme: "dark",
  colors: darkColors,
  gradients: darkGradients,
  type: buildType(darkColors),
};

const styleEntries: Array<{
  factory: () => Record<string, unknown>;
  current: Record<string, unknown>;
}> = [];

export function getColorScheme(): ColorSchemeName {
  return active.scheme;
}

export function applyScheme(scheme: ColorSchemeName) {
  const colors = scheme === "light" ? lightColors : darkColors;
  active = {
    scheme,
    colors,
    gradients: scheme === "light" ? lightGradients : darkGradients,
    type: buildType(colors),
  };
  for (const entry of styleEntries) {
    entry.current = entry.factory();
  }
}

/**
 * StyleSheet.create freezes colors. Register the factory so a system theme
 * change rebuilds the sheet, and read it through a proxy so existing
 * `styles.foo` call sites pick up the new values on the next render.
 */
export function registerStyles<T extends Record<string, unknown>>(factory: () => T): T {
  const entry = {
    factory: factory as () => Record<string, unknown>,
    current: factory() as Record<string, unknown>,
  };
  styleEntries.push(entry);
  return new Proxy({} as T, {
    get(_target, key: string) {
      return entry.current[key];
    },
  });
}

function live<T extends object>(read: () => T): T {
  return new Proxy({} as T, {
    get(_target, key: string) {
      return read()[key as keyof T];
    },
  });
}

export const colors: Palette = live(() => active.colors);
export const gradients: GradientSet = live(() => active.gradients);
export const type: TypeScale = live(() => active.type);

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
