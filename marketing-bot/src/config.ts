import "dotenv/config";
import { z } from "zod";

const envSchema = z.object({
  PORT: z.coerce.number().int().positive().default(8787),
  PUBLIC_BASE_URL: z.string().url().default("http://localhost:8787"),
  ADMIN_KEY: z.string().min(12).default("change-me-before-deploying"),
  YWP_OS_API_BASE_URL: z.string().url().default("https://ywp-os-api.onrender.com"),
  YWP_OS_MARKETING_FEED_PATH: z.string().startsWith("/").default("/api/v1/marketing/approved-cards"),
  YWP_OS_API_TOKEN: z.string().default(""),
  IG_PUBLISH_ENABLED: z.enum(["true", "false"]).default("false"),
  IG_USER_ID: z.string().default(""),
  IG_ACCESS_TOKEN: z.string().default(""),
  META_GRAPH_VERSION: z.string().regex(/^v\d+\.\d+$/).default("v24.0"),
  YWP_TIMEZONE: z.string().default("America/New_York")
});

const env = envSchema.parse(process.env);

export const config = {
  port: env.PORT,
  publicBaseUrl: env.PUBLIC_BASE_URL.replace(/\/$/, ""),
  adminKey: env.ADMIN_KEY,
  ywpApiBaseUrl: env.YWP_OS_API_BASE_URL.replace(/\/$/, ""),
  ywpMarketingFeedPath: env.YWP_OS_MARKETING_FEED_PATH,
  ywpApiToken: env.YWP_OS_API_TOKEN,
  instagramPublishEnabled: env.IG_PUBLISH_ENABLED === "true",
  instagramUserId: env.IG_USER_ID,
  instagramAccessToken: env.IG_ACCESS_TOKEN,
  metaGraphVersion: env.META_GRAPH_VERSION,
  timezone: env.YWP_TIMEZONE
};
