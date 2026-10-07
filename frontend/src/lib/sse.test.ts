import { describe, expect, it } from "vitest";

import { parseSse, readSse } from "./sse";

describe("parseSse", () => {
  it("parses complete events and keeps the unfinished tail", () => {
    const buffer =
      'event: delta\ndata: {"text":"Hej"}\n\n' + 'event: done\ndata: {"refused":false}\n\n' + "event: del";

    const { events, rest } = parseSse(buffer);

    expect(events).toEqual([
      { event: "delta", data: { text: "Hej" } },
      { event: "done", data: { refused: false } },
    ]);
    expect(rest).toBe("event: del");
  });

  it("returns nothing until an event is terminated by a blank line", () => {
    expect(parseSse('event: delta\ndata: {"text":"a"}')).toEqual({
      events: [],
      rest: 'event: delta\ndata: {"text":"a"}',
    });
  });

  it("skips malformed events instead of throwing", () => {
    const { events } = parseSse('event: delta\ndata: {broken\n\nevent: done\ndata: {"ok":true}\n\n');

    expect(events).toEqual([{ event: "done", data: { ok: true } }]);
  });
});

describe("readSse", () => {
  it("reassembles events split across network chunks", async () => {
    const encoder = new TextEncoder();
    const chunks = ['event: delta\ndata: {"te', 'xt":"Zażółć"}\n\nevent: done\n', 'data: {"sources":[]}\n\n'];
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    });

    const events = [];
    for await (const event of readSse(new Response(stream))) events.push(event);

    expect(events).toEqual([
      { event: "delta", data: { text: "Zażółć" } },
      { event: "done", data: { sources: [] } },
    ]);
  });
});
