import { buildUrl } from "./client";

const INTERNAL_API_URL =
  process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

/**
 * Fetch public data from a server component. Returns null on 404 and throws on
 * other failures so the nearest error boundary renders.
 */
export async function fetchPublic<T>(
  path: string,
  query: Record<string, string | number | undefined> = {},
): Promise<T | null> {
  const response = await fetch(buildUrl(INTERNAL_API_URL, `/public${path}`, query), {
    next: { revalidate: 60 },
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`API responded with ${response.status} for ${path}`);
  return (await response.json()) as T;
}
