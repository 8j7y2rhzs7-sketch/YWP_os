export const API_URL = (
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");

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
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
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
