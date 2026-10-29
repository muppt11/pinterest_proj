import { useEffect, useRef, useState, type FormEvent } from "react";
import { altText, api, imageSrc, startAssistantChat, type AssistantRequest, type ChatTurn, type Item } from "../api/client";
import { streamSse } from "../api/sse";
import "./AssistantPanel.css";

interface Message {
  role: "user" | "assistant";
  text: string;
  items?: Item[];
  itemsSource?: "cited" | "tool results";
  activity?: string[];
  error?: boolean;
  pending?: boolean;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onOpenItem: (item: Item) => void;
  contextItemIds: string[];
  board: AssistantRequest["board"];
}

const TOOL_LABELS: Record<string, string> = {
  search_similar: "Searching the catalog",
  complete_look: "Building an outfit",
  compare_items: "Comparing items",
  describe_board: "Reading your board",
};

/** Suggested questions that fit what you're looking at (each one is in the assistant eval set or close to it). */
export function suggestionsFor(hasItem: boolean, hasBoard: boolean): string[] {
  const item = ["What shoes would finish this look?", "What goes with this for a dinner out?", "Find something like this in a different color"];
  const board = ["Describe my board's style", "Build an outfit from my board's main aesthetic"];
  const general = [
    "Find a black leather jacket",
    "What should I wear to a summer beach wedding?",
    "Build a cozy outfit for a rainy autumn day",
    "Show me pastel tops for spring",
    "Find kids' sneakers",
  ];
  return [...(hasItem ? item : []), ...(hasBoard ? board : []), ...general].slice(0, 5);
}

/** Replace [item:ID] citations with the item's position in the cards below, e.g. "(1)". */
function renderCitations(text: string, items: Item[]): string {
  return text.replace(/\[item:([A-Za-z0-9_-]+)\]/g, (_, id: string) => {
    const index = items.findIndex((i) => i.id === id);
    return index >= 0 ? `(${index + 1})` : "";
  });
}

/** Right-side chat drawer for the style assistant. Products shown come only from validated tool results. */
export function AssistantPanel({ open, onClose, onOpenItem, contextItemIds, board }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abort = useRef<AbortController | null>(null);
  // null = still checking; otherwise whether the local model is ready.
  const [status, setStatus] = useState<{ available: boolean; model: string; reason: string | null } | null>(null);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    api
      .assistantStatus()
      .then(setStatus)
      .catch(() => setStatus({ available: false, model: "", reason: "api_unreachable" }));
  }, [open]);

  useEffect(() => () => abort.current?.abort(), []);

  function update(fn: (last: Message) => Message) {
    setMessages((prev) => [...prev.slice(0, -1), fn(prev[prev.length - 1])]);
  }

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const history: ChatTurn[] = messages
      .filter((m) => !m.error && !m.pending)
      .map((m) => ({ role: m.role, content: m.text }));
    setMessages((prev) => [...prev, { role: "user", text: message }, { role: "assistant", text: "", activity: [], pending: true }]);
    setInput("");
    setBusy(true);
    abort.current = new AbortController();
    try {
      const response = await startAssistantChat(
        { message, history, context_item_ids: contextItemIds, board },
        abort.current.signal,
      );
      let finished = false;
      for await (const { event, data } of streamSse(response)) {
        const d = data as Record<string, unknown>;
        if (event === "tool") {
          const label = TOOL_LABELS[d.name as string] ?? (d.name as string);
          update((m) => ({ ...m, activity: [...(m.activity ?? []), label] }));
        } else if (event === "done") {
          const items = d.items as Item[];
          const itemsSource = (d.items_source as Message["itemsSource"]) ?? "cited";
          update((m) => ({ ...m, text: renderCitations(d.text as string, items), items, itemsSource, pending: false }));
          finished = true;
          break;
        } else if (event === "error") {
          update((m) => ({ ...m, text: d.message as string, error: true, pending: false }));
          finished = true;
          break;
        }
      }
      if (!finished) {
        update((m) => ({ ...m, text: "The response ended before it finished. Please try again.", error: true, pending: false }));
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        update((m) => ({ ...m, text: "Couldn't reach the assistant. Is the API running?", error: true, pending: false }));
      }
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  if (!open) return null;

  return (
    <aside className="mb-assistant" aria-label="Style assistant">
      <header className="mb-assistant-head">
        <h2>Style assistant</h2>
        <button type="button" className="mb-icon-button" aria-label="Close assistant" onClick={onClose}>
          ×
        </button>
      </header>
      <p className="mb-assistant-note">
        Every item it shows comes from a catalog search
      </p>

      <ol className="mb-assistant-log" aria-live="polite">
        {status && !status.available && (
          <li className="mb-assistant-setup" role="status">
            <strong>The assistant runs on a local AI model, and it isn't set up on this computer yet.</strong>
            {status.reason === "api_unreachable" ? (
              <p>Couldn't reach the MoodBoards API. Is the backend running?</p>
            ) : (
              <>
                <p>To turn it on, install Ollama and download the model once:</p>
                <pre>
                  {status.reason === "ollama_not_running" ? "open -a Ollama\n" : ""}ollama pull {status.model}
                </pre>
                <p>Everything else in MoodBoards works without it.</p>
              </>
            )}
          </li>
        )}

        {messages.length === 0 && status?.available !== false && (
          <li className="mb-assistant-suggestions">
            <span className="mb-assistant-suggest-label">Try asking</span>
            {suggestionsFor(contextItemIds.length > 0, !!board).map((s) => (
              <button key={s} type="button" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </li>
        )}
        {messages.map((m, i) => (
          <li key={i} className={`mb-msg mb-msg-${m.role}${m.error ? " is-error" : ""}`}>
            {m.activity && m.activity.length > 0 && (
              <ul className="mb-msg-activity" aria-label="What the assistant did">
                {m.activity.map((a, j) => (
                  <li key={j}>{a}…</li>
                ))}
              </ul>
            )}
            {m.text ? <p>{m.text}</p> : m.pending && <p className="mb-msg-typing">Thinking…</p>}
            {m.items && m.items.length > 0 && m.itemsSource === "tool results" && (
              <p className="mb-msg-source">From the catalog search:</p>
            )}
            {m.items && m.items.length > 0 && (
              <ul className="mb-msg-items">
                {m.items.map((item, j) => (
                  <li key={item.id}>
                    <button type="button" onClick={() => onOpenItem(item)} aria-label={`Open item ${j + 1}: ${item.category}`}>
                      <img src={imageSrc(item)} alt={altText(item)} loading="lazy" />
                      <span>
                        {j + 1}. {item.category}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>

      <form className="mb-assistant-input" onSubmit={submit}>
        <label htmlFor="mb-assistant-text" className="visually-hidden">
          Ask the style assistant
        </label>
        <textarea
          id="mb-assistant-text"
          ref={inputRef}
          disabled={status?.available === false}
          rows={2}
          value={input}
          placeholder="Ask about outfits…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
            if (e.key === "Escape") onClose();
          }}
        />
        <button type="submit" className="mb-button-primary" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </aside>
  );
}
