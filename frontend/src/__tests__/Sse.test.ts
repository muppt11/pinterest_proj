import { parseSse, streamSse } from "../api/sse";

describe("SSE transport", () => {
  it("parses CRLF events and retains partial delimiters", () => {
    const first = parseSse('event: done\r\ndata: {"text":"ok"}\r');
    expect(first.events).toEqual([]);
    expect(parseSse(first.rest + '\n\r\n').events).toEqual([{ event: "done", data: { text: "ok" } }]);
  });

  it("decodes UTF-8 split across network chunks", async () => {
    const bytes = new TextEncoder().encode('event: done\r\ndata: {"text":"café"}\r\n\r\n');
    const split = bytes.indexOf(0xc3) + 1;
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, split));
        controller.enqueue(bytes.slice(split));
        controller.close();
      },
    });
    const events = [];
    for await (const event of streamSse(new Response(body))) events.push(event);
    expect(events).toEqual([{ event: "done", data: { text: "café" } }]);
    expect(body.locked).toBe(false);
  });

  it("cancels and releases the stream when the consumer finishes early", async () => {
    const cancel = vi.fn();
    const body = new ReadableStream<Uint8Array>({
      start(controller) { controller.enqueue(new TextEncoder().encode('event: done\ndata: {}\n\n')); },
      cancel,
    });
    for await (const event of streamSse(new Response(body))) {
      expect(event.event).toBe("done");
      break;
    }
    expect(cancel).toHaveBeenCalledOnce();
    expect(body.locked).toBe(false);
  });
});
