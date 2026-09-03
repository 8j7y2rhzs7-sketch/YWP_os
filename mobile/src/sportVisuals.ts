export const sportLooks: Record<
  string,
  { emoji: string; accent: string; field: string; glow: string; label: string }
> = {
  mlb: { emoji: "⚾", accent: "#41B6E6", field: "#0E3A2C", glow: "#F5C542", label: "DIAMOND" },
  wnba: { emoji: "🏀", accent: "#FF6B35", field: "#3A1840", glow: "#FFD166", label: "HARDWOOD" },
  basketball: { emoji: "🏀", accent: "#FF6B35", field: "#3A1840", glow: "#FFD166", label: "HARDWOOD" },
  nba: { emoji: "🏀", accent: "#C8102E", field: "#1C1230", glow: "#FDB927", label: "HARDWOOD" },
  nfl: { emoji: "🏈", accent: "#C4A35A", field: "#16351C", glow: "#F5C542", label: "GRIDIRON" },
  ncaaf: { emoji: "🏈", accent: "#E94F37", field: "#16351C", glow: "#F4D35E", label: "CAMPUS" },
  soccer: { emoji: "⚽", accent: "#2ECC71", field: "#12351F", glow: "#F5C542", label: "PITCH" },
  nhl: { emoji: "🏒", accent: "#8AD4FF", field: "#0E2438", glow: "#F8F9FB", label: "RINK" },
  kbo: { emoji: "⚾", accent: "#F4D35E", field: "#0E3A2C", glow: "#F5C542", label: "KBO" },
};

export function sportLook(sport?: string) {
  return sportLooks[(sport ?? "").toLowerCase()] ?? sportLooks.mlb;
}
