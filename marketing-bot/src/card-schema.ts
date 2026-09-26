import { z } from "zod";

const legSchema = z.object({
  id: z.string().min(1),
  event: z.string().min(2),
  selection: z.string().min(2),
  market: z.string().min(2),
  line: z.string().nullable().optional(),
  price: z.string().nullable().optional()
});

export const marketingCardSchema = z.object({
  id: z.string().min(1),
  sport: z.string().min(2),
  title: z.string().min(2),
  status: z.enum(["VERIFIED", "PARTIAL", "REVIEW", "SKIP", "DEMO", "EXPIRED"]),
  publicationEligible: z.boolean(),
  demo: z.boolean(),
  sportsbook: z.string().nullable().optional(),
  eventStart: z.string().datetime({ offset: true }),
  verifiedAsOf: z.string().datetime({ offset: true }),
  expiresAt: z.string().datetime({ offset: true }),
  ywpScore: z.number().min(0).max(100).nullable().optional(),
  modelProbability: z.number().min(0).max(1).nullable().optional(),
  dataQuality: z.string().nullable().optional(),
  sourceVersion: z.string().nullable().optional(),
  legs: z.array(legSchema).min(1).max(5)
});

export const marketingFeedSchema = z.object({
  generatedAt: z.string().datetime({ offset: true }),
  cards: z.array(marketingCardSchema)
});
