export type SportLook = {
  emoji: string;
  accent: string;
  accentSoft: string;
  field: string;
  glow: string;
  stripe: string;
  page: readonly [string, string, string];
  label: string;
};

/** Jersey / venue energy per sport — gold stays brand, accents follow the game. */
export const sportLooks: Record<string, SportLook> = {
  mlb: {
    emoji: "⚾",
    accent: "#3DB8FF",
    accentSoft: "rgba(61,184,255,0.18)",
    field: "#0A2F24",
    glow: "#F0C14A",
    stripe: "#E8F4FF",
    page: ["#031812", "#05090E", "#0A1208"],
    label: "DIAMOND",
  },
  wnba: {
    emoji: "🏀",
    accent: "#FF6A3D",
    accentSoft: "rgba(255,106,61,0.18)",
    field: "#1A1208",
    glow: "#FFC857",
    stripe: "#FFE0C8",
    page: ["#140C06", "#080A0E", "#1A1008"],
    label: "HARDWOOD",
  },
  basketball: {
    emoji: "🏀",
    accent: "#FF6A3D",
    accentSoft: "rgba(255,106,61,0.18)",
    field: "#1A1208",
    glow: "#FFC857",
    stripe: "#FFE0C8",
    page: ["#140C06", "#080A0E", "#1A1008"],
    label: "HARDWOOD",
  },
  nba: {
    emoji: "🏀",
    accent: "#E31837",
    accentSoft: "rgba(227,24,55,0.18)",
    field: "#1A1408",
    glow: "#FDB927",
    stripe: "#FFD76A",
    page: ["#160808", "#080A10", "#141008"],
    label: "HARDWOOD",
  },
  nfl: {
    emoji: "🏈",
    accent: "#D4A84B",
    accentSoft: "rgba(212,168,75,0.18)",
    field: "#0E2A16",
    glow: "#F0C14A",
    stripe: "#FFFFFF",
    page: ["#06140C", "#06090C", "#121008"],
    label: "GRIDIRON",
  },
  ncaaf: {
    emoji: "🏈",
    accent: "#E94F37",
    accentSoft: "rgba(233,79,55,0.18)",
    field: "#0E2A16",
    glow: "#F4D35E",
    stripe: "#FFD27A",
    page: ["#0A160C", "#080A0C", "#180C08"],
    label: "CAMPUS",
  },
  soccer: {
    emoji: "⚽",
    accent: "#2EE59A",
    accentSoft: "rgba(46,229,154,0.16)",
    field: "#0A2818",
    glow: "#4DB8FF",
    stripe: "#E8FFF4",
    page: ["#041810", "#050A12", "#061018"],
    label: "PITCH",
  },
  nhl: {
    emoji: "🏒",
    accent: "#7EC8FF",
    accentSoft: "rgba(126,200,255,0.18)",
    field: "#0A1C2C",
    glow: "#F8F9FB",
    stripe: "#FFFFFF",
    page: ["#040C16", "#05080C", "#0A1218"],
    label: "RINK",
  },
  kbo: {
    emoji: "⚾",
    accent: "#F4D35E",
    accentSoft: "rgba(244,211,94,0.18)",
    field: "#0A2F24",
    glow: "#F0C14A",
    stripe: "#FFF4C8",
    page: ["#031812", "#05090E", "#0A1208"],
    label: "KBO",
  },
};

const DEFAULT_SPORT_LOOK: SportLook = {
  emoji: "⚾",
  accent: "#3DB8FF",
  accentSoft: "rgba(61,184,255,0.18)",
  field: "#0A2F24",
  glow: "#F0C14A",
  stripe: "#E8F4FF",
  page: ["#031812", "#05090E", "#0A1208"],
  label: "DIAMOND",
};

export function sportLook(sport?: string): SportLook {
  return sportLooks[(sport ?? "").toLowerCase()] ?? DEFAULT_SPORT_LOOK;
}
