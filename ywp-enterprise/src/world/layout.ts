/** Tile positions for the overworld factory (Pokémon-style top-down). */

export interface StationPos {
  id: string;
  x: number; // tile col
  y: number; // tile row
  label: string;
  kind: "boss" | "design" | "pod" | "venture" | "vault" | "path";
}

export const TILE = 32;
export const MAP_COLS = 18;
export const MAP_ROWS = 12;

/** Logical stations agents walk between */
export const STATIONS: StationPos[] = [
  { id: "room-boss", x: 2, y: 2, label: "BOSS", kind: "boss" },
  { id: "room-design", x: 5, y: 2, label: "DESIGN", kind: "design" },
  { id: "vault", x: 9, y: 5, label: "VAULT", kind: "vault" },
  { id: "room-mugs", x: 2, y: 7, label: "MUGS", kind: "pod" },
  { id: "room-candles", x: 5, y: 7, label: "CANDLES", kind: "pod" },
  { id: "room-personal", x: 8, y: 7, label: "CUSTOM", kind: "pod" },
  { id: "room-ads", x: 12, y: 2, label: "ADS", kind: "venture" },
  { id: "room-fiverr", x: 15, y: 2, label: "GIGS", kind: "venture" },
  { id: "room-shopify", x: 12, y: 5, label: "SHOP", kind: "venture" },
  { id: "room-digital", x: 15, y: 5, label: "FILES", kind: "venture" },
  { id: "room-content", x: 12, y: 8, label: "CLIPS", kind: "venture" },
  { id: "room-affiliate", x: 15, y: 8, label: "LINKS", kind: "venture" },
  { id: "room-merch", x: 2, y: 10, label: "MERCH", kind: "venture" },
  { id: "room-newsletter", x: 5, y: 10, label: "NEWS", kind: "venture" },
  { id: "room-youtube", x: 8, y: 10, label: "TUBE", kind: "venture" },
  { id: "room-wholesale", x: 11, y: 10, label: "BULK", kind: "venture" },
  { id: "room-saas", x: 14, y: 10, label: "SAAS", kind: "venture" },
  { id: "room-leads", x: 16, y: 10, label: "LEADS", kind: "venture" },
];

export function stationCenter(id: string): { x: number; y: number } {
  const s = STATIONS.find((st) => st.id === id) ?? STATIONS[0]!;
  return {
    x: s.x * TILE + TILE / 2,
    y: s.y * TILE + TILE / 2,
  };
}

export type CargoKind = "coin" | "mug" | "box" | "scroll";

export interface Walker {
  id: string;
  agentId: string;
  name: string;
  role: string;
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  facing: "down" | "up" | "left" | "right";
  carrying: CargoKind | null;
  palette: number;
}

export interface FlyingCargo {
  id: string;
  kind: CargoKind;
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  born: number;
}
