export type MarketingLeg = {
  id: string;
  event: string;
  selection: string;
  market: string;
  line?: string | null;
  price?: string | null;
};

export type MarketingCard = {
  id: string;
  sport: string;
  title: string;
  status: "VERIFIED" | "PARTIAL" | "REVIEW" | "SKIP" | "DEMO" | "EXPIRED";
  publicationEligible: boolean;
  demo: boolean;
  sportsbook?: string | null;
  eventStart: string;
  verifiedAsOf: string;
  expiresAt: string;
  ywpScore?: number | null;
  modelProbability?: number | null;
  dataQuality?: string | null;
  sourceVersion?: string | null;
  legs: MarketingLeg[];
};

export type DraftStatus = "DRAFT" | "APPROVED" | "PUBLISHED" | "BLOCKED";

export type MarketingDraft = {
  id: string;
  cardId: string;
  createdAt: string;
  updatedAt: string;
  status: DraftStatus;
  caption: string;
  imageFilename: string;
  blockReasons: string[];
  approvedAt?: string;
  publishedAt?: string;
  instagramMediaId?: string;
  card: MarketingCard;
};
