export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail);
  }
}

export interface ApiRequest {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string;
  query?: Record<string, string | number | undefined>;
}

export function buildUrl(base: string, path: string, query: ApiRequest["query"] = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const suffix = params.size > 0 ? `?${params}` : "";
  return `${base}${path}${suffix}`;
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    return typeof payload.detail === "string" ? payload.detail : response.statusText;
  } catch {
    return response.statusText;
  }
}

export async function apiFetch<T>(path: string, request: ApiRequest = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (request.body !== undefined) headers["Content-Type"] = "application/json";
  if (request.token) headers.Authorization = `Bearer ${request.token}`;

  const response = await fetch(buildUrl(API_URL, path, request.query), {
    method: request.method ?? "GET",
    headers,
    body: request.body === undefined ? undefined : JSON.stringify(request.body),
  });
  if (!response.ok) throw new ApiError(response.status, await errorDetail(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
