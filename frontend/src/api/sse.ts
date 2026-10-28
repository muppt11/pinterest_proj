/** Minimal Server-Sent Events reader for POST responses (EventSource only supports GET). */
export interface SseEvent {
  event: string;
  data: unknown;
}

/** Parse complete `event:`/`data:` blocks out of a buffer; returns parsed events and the leftover text. */
export function parseSse(buffer: string): { events: SseEvent[]; rest: string } {
  const events: SseEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (data.length === 0) continue;
    try {
      events.push({ event, data: JSON.parse(data.join("\n")) });
    } catch {
      events.push({ event, data: data.join("\n") });
    }
  }
  return { events, rest };
}

export async function* streamSse(response: Response): AsyncGenerator<SseEvent> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSse(buffer);
    buffer = rest;
    yield* events;
  }
  const { events } = parseSse(buffer + "\n\n");
  yield* events;
}
