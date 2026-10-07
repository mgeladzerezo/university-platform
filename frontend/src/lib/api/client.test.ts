import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiError, buildUrl } from "./client";

afterEach(() => vi.unstubAllGlobals());

function stubFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("buildUrl", () => {
  it("drops empty and undefined query values and encodes the rest", () => {
    const url = buildUrl("http://api/v1", "/public/programs", {
      q: "analiza danych",
      level: undefined,
      faculty: "",
      locale: "pl",
    });

    expect(url).toBe("http://api/v1/public/programs?q=analiza+danych&locale=pl");
  });
});

describe("apiFetch", () => {
  it("sends the bearer token and JSON body", async () => {
    const fetchMock = stubFetch(Response.json({ id: 1 }));

    await apiFetch("/cms/content", { method: "POST", body: { title: "x" }, token: "abc" });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers).toEqual({ "Content-Type": "application/json", Authorization: "Bearer abc" });
    expect(init.body).toBe('{"title":"x"}');
  });

  it("throws ApiError carrying the API detail message", async () => {
    stubFetch(Response.json({ detail: "Already enrolled or waitlisted" }, { status: 409 }));

    const error = await apiFetch("/academics/offerings/1/enrollment", { method: "POST" }).catch(
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as ApiError).message).toBe("Already enrolled or waitlisted");
  });

  it("returns undefined for 204 responses", async () => {
    stubFetch(new Response(null, { status: 204 }));

    await expect(apiFetch("/x", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
