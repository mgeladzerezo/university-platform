import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/en.json";

import { ChatWidget } from "./ChatWidget";

afterEach(() => vi.unstubAllGlobals());

function sseResponse(body: string, status = 200): Response {
  return new Response(body, { status, headers: { "Content-Type": "text/event-stream" } });
}

async function openAndAsk(question: string) {
  const user = userEvent.setup();
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <ChatWidget />
    </NextIntlClientProvider>,
  );
  await user.click(screen.getByRole("button", { name: "Open assistant" }));
  await user.type(screen.getByLabelText("Your question"), question);
  await user.click(screen.getByRole("button", { name: "Ask" }));
}

describe("ChatWidget", () => {
  it("streams the answer and lists source links", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse(
        'event: delta\ndata: {"text":"The deadline is "}\n\n' +
          'event: delta\ndata: {"text":"10 July [1]."}\n\n' +
          'event: done\ndata: {"refused":false,"sources":[{"id":1,"title":"Admission deadlines","path":"/en/pages/admission-deadlines"}]}\n\n',
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await openAndAsk("When is the deadline?");

    expect(await screen.findByText("The deadline is 10 July [1].")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Admission deadlines" })).toHaveAttribute(
      "href",
      "/en/pages/admission-deadlines",
    );
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/assistant\/chat$/);
    expect(JSON.parse(init.body)).toEqual({ question: "When is the deadline?", locale: "en" });
    expect(init.headers).not.toHaveProperty("Authorization");
  });

  it("renders model output as text, never as HTML", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse(
          'event: delta\ndata: {"text":"<img src=x onerror=alert(1)>"}\n\n' +
            'event: done\ndata: {"refused":false,"sources":[]}\n\n',
        ),
      ),
    );

    await openAndAsk("Anything?");

    expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });

  it("explains rate limiting", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse("", 429)));

    await openAndAsk("One more question");

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Too many questions"),
    );
  });
});
