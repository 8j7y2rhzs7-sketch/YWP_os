import AsyncStorage from "@react-native-async-storage/async-storage";

const API_URL_KEY = "ywp.os.api_url.v1";
const DEFAULT_API_URL = (
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");

let currentApiUrl = DEFAULT_API_URL;

export function getApiUrl(): string {
  return currentApiUrl;
}

export const API_URL = DEFAULT_API_URL;

export function normalizeApiUrl(value: string): string {
  return value.trim().replace(/\/$/, "");
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
  if (!next) {
    throw new Error("Enter your YWP OS API URL");
  }
  currentApiUrl = next;
  await AsyncStorage.setItem(API_URL_KEY, next);
  return next;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
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
    const message =
      typeof detail === "string"
        ? detail
        : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, detail);
  }
  return body as T;
}
