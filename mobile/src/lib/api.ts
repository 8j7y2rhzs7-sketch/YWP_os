import AsyncStorage from "@react-native-async-storage/async-storage";

const API_URL_KEY = "ywp.os.api_url.v1";
const configuredApiUrl = process.env.EXPO_PUBLIC_API_URL?.trim();
const DEFAULT_API_URL = (
  configuredApiUrl || (__DEV__ ? "http://localhost:8000/api/v1" : "")
).replace(/\/$/, "");

let currentApiUrl = DEFAULT_API_URL;

export function getApiUrl(): string {
  return currentApiUrl;
}

export const WHOP_CHECKOUT_URL =
  process.env.EXPO_PUBLIC_WHOP_CHECKOUT_URL ??
  process.env.NEXT_PUBLIC_WHOP_CHECKOUT_URL ??
  "https://whop.com/checkout/plan_MwJ2qcFxmvqDY";

export function normalizeApiUrl(value: string): string {
  const normalized = value.trim().replace(/\/$/, "");
  if (!normalized) throw new Error("Enter your deployed YWP OS API URL");
  let parsed: URL;
  try {
    parsed = new URL(normalized);
  } catch {
    throw new Error("Enter a complete API URL beginning with https://");
  }
  const localDevelopment = ["localhost", "127.0.0.1", "10.0.2.2"].includes(
    parsed.hostname,
  );
  if (parsed.protocol !== "https:" && !(__DEV__ && localDevelopment)) {
    throw new Error("Production API connections must use HTTPS");
  }
  if (!parsed.pathname.endsWith("/api/v1")) {
    throw new Error("The API URL must end with /api/v1");
  }
  return normalized;
}

export async function loadApiUrl(): Promise<string> {
  try {
    const stored = await AsyncStorage.getItem(API_URL_KEY);
    if (stored) {
      currentApiUrl = stored.replace(/\/$/, "");
    }
  } catch {
    // keep compiled default
  }
  return currentApiUrl;
}

export async function saveApiUrl(value: string): Promise<string> {
  const next = normalizeApiUrl(value);
  currentApiUrl = next;
  await AsyncStorage.setItem(API_URL_KEY, next);
  return next;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
    public readonly checkoutUrl?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function rawRequest<T>(
  path: string,
  init: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  if (!getApiUrl()) {
    throw new ApiError(
      "This build has no backend configured. Add EXPO_PUBLIC_API_URL during the build or save the Render /api/v1 address in Settings.",
      503,
    );
  }
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const response = await fetch(`${getApiUrl()}${path}`, { ...init, headers });
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? body.detail
        : body;
    const checkoutUrl =
      typeof detail === "object" &&
      detail !== null &&
      "checkout_url" in detail &&
      typeof detail.checkout_url === "string"
        ? detail.checkout_url
        : undefined;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" &&
            detail !== null &&
            "message" in detail &&
            typeof detail.message === "string"
          ? detail.message
          : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, detail, checkoutUrl);
  }
  return body as T;
}
