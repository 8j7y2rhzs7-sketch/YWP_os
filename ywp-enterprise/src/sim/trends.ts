import type { ProductKind, TrendNiche } from "./types";

/** Market demand niches — categories only, never competitor artwork. */
export const SEED_NICHES: TrendNiche[] = [
  { id: "nurse-life", label: "Nurse appreciation", demand: 0.86, tags: ["healthcare", "gift"] },
  { id: "dog-dad", label: "Dog dad / pet parent", demand: 0.82, tags: ["pets", "humor"] },
  { id: "teacher-fuel", label: "Teacher fuel", demand: 0.78, tags: ["education", "mug"] },
  { id: "wedding-party", label: "Wedding party names", demand: 0.74, tags: ["personalized", "event"] },
  { id: "gamer-den", label: "Gamer den", demand: 0.71, tags: ["gaming", "home"] },
  { id: "new-home", label: "First home coordinates", demand: 0.69, tags: ["personalized", "home"] },
  { id: "book-club", label: "Book club nights", demand: 0.64, tags: ["reading", "candle"] },
  { id: "plant-mom", label: "Plant mom", demand: 0.67, tags: ["plants", "humor"] },
  { id: "retirement", label: "Retirement countdown", demand: 0.6, tags: ["milestone"] },
  { id: "sports-mom", label: "Sideline sports mom", demand: 0.72, tags: ["sports", "family"] },
];

const PRODUCT_LINE: Record<ProductKind, string[]> = {
  mug: ["ceramic mug", "enamel camp mug", "latte mug"],
  candle: ["soy candle tin", "glass jar candle", "travel tin"],
  personalized: ["name-custom print", "date-custom print", "monogram print"],
};

const STYLE_SEEDS = [
  "clean mid-century line illustration",
  "bold typographic lockup with one accent shape",
  "soft watercolor wash behind simple icons",
  "retro badge seal with modern spacing",
  "hand-lettered headline over subtle texture",
];

function pick<T>(arr: T[], salt: number): T {
  return arr[Math.abs(salt) % arr.length]!;
}

/** Build an original design brief from a hot niche — never “copy listing X”. */
export function inventOriginalBrief(
  niche: TrendNiche,
  product: ProductKind,
  salt: number,
): { title: string; designBrief: string } {
  const vessel = pick(PRODUCT_LINE[product], salt);
  const style = pick(STYLE_SEEDS, salt + 3);
  const hook = pick(
    [
      `${niche.label} — original mark`,
      `Made for ${niche.label.toLowerCase()}`,
      `${niche.tags[0] ?? "gift"} story edition`,
    ],
    salt + 7,
  );

  const title = `${hook} ${vessel}`.replace(/\b\w/g, (c) => c.toUpperCase());
  const designBrief = [
    `ORIGINAL artwork only. Niche demand signal: "${niche.label}".`,
    `Product: ${vessel}. Visual direction: ${style}.`,
    `Include tasteful negative space; no brand logos, no celebrity likeness,`,
    `no tracing or recreating another seller's design.`,
    `Palette pulled from niche mood (${niche.tags.join(", ")}).`,
  ].join(" ");

  return { title, designBrief };
}

export function driftNicheDemand(niches: TrendNiche[], day: number): TrendNiche[] {
  return niches.map((n, i) => {
    const wave = Math.sin(day * 0.35 + i * 1.7) * 0.06;
    const demand = Math.min(0.95, Math.max(0.35, n.demand + wave));
    return { ...n, demand };
  });
}
