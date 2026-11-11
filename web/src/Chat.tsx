import { type ReactNode, useEffect, useRef, useState } from "react";

import { chat, resetChat } from "./api";
import type { Status } from "./types";

type Step = { name: string; input: Record<string, unknown> };
type Message =
  | { role: "user"; text: string }
  | { role: "assistant"; text: string; steps: Step[]; error?: string; pending: boolean };

const SUGGESTIONS = [
  "Which scenes could be shot on the same day?",
  "Who has the most dialogue, and in which scenes?",
  "Summarize the story in five lines.",
];

function describeStep(step: Step): string {
  const input = step.input ?? {};
  switch (step.name) {
    case "list_scenes":
      return "Looked at the scene list";
    case "read_scenes": {
      const numbers = Array.isArray(input.numbers) ? input.numbers.map(String) : [];
      return numbers.length ? `Read scene${numbers.length > 1 ? "s" : ""} ${numbers.join(", ")}` : "Read scenes";
    }
    case "list_characters":
      return "Checked the cast";
    case "character_dialogue":
      return `Read ${typeof input.name === "string" ? input.name : "a character"}'s dialogue`;
    case "list_locations":
      return "Checked the locations";
    case "search_script":
      return `Searched for "${typeof input.query === "string" ? input.query : ""}"`;
    case "format_issues":
      return "Checked the formatting";
    default:
      return step.name;
  }
}

/** Bold, italics and code inside one line of the assistant's answer. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) return <code key={i}>{part.slice(1, -1)}</code>;
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) return <em key={i}>{part.slice(1, -1)}</em>;
    return part;
  });
}

/** The small subset of Markdown the assistant uses: paragraphs, lists, headings. */
function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let paragraph: string[] = [];
  const flush = () => {
    if (paragraph.length) {
      blocks.push(<p key={blocks.length}>{paragraph.flatMap((line, i) => (i ? [<br key={`b${i}`} />, ...inline(line)] : inline(line)))}</p>);
      paragraph = [];
    }
    if (list) {
      const items = list.items.map((item, i) => <li key={i}>{inline(item)}</li>);
      blocks.push(list.ordered ? <ol key={blocks.length}>{items}</ol> : <ul key={blocks.length}>{items}</ul>);
      list = null;
    }
  };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    if (!line.trim()) {
      flush();
    } else if (heading) {
      flush();
      blocks.push(
        <p key={blocks.length}>
          <strong>{inline(heading[1])}</strong>
        </p>,
      );
    } else if (bullet || numbered) {
      const ordered = !bullet;
      if (paragraph.length || (list && list.ordered !== ordered)) flush();
      list ??= { ordered, items: [] };
      list.items.push((bullet ?? numbered)![1]);
    } else {
      if (list) flush();
      paragraph.push(line);
    }
  }
  flush();
  return <>{blocks}</>;
}

export default function Chat(props: { scriptId: string; title: string; status: Status | null; onClose: () => void }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const session = useRef(crypto.randomUUID());
  const abort = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const available = props.status?.llm.available ?? false;

  // A different script is a different conversation.
  useEffect(() => {
    abort.current?.abort();
    session.current = crypto.randomUUID();
    setMessages([]);
    setBusy(false);
  }, [props.scriptId]);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  useEffect(() => {
    input.current?.focus();
  }, []);

  const patch = (change: (m: Extract<Message, { role: "assistant" }>) => void) =>
    setMessages((all) => {
      const last = all[all.length - 1];
      if (!last || last.role !== "assistant") return all;
      const copy = { ...last, steps: [...last.steps] };
      change(copy);
      return [...all.slice(0, -1), copy];
    });

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    setDraft("");
    setBusy(true);
    setMessages((all) => [...all, { role: "user", text: question }, { role: "assistant", text: "", steps: [], pending: true }]);
    abort.current = new AbortController();
    try {
      await chat(
        props.scriptId,
        session.current,
        question,
        (event) => {
          if (event.type === "text") patch((m) => void (m.text += event.text));
          else if (event.type === "tool") patch((m) => void m.steps.push({ name: event.name, input: event.input }));
          else if (event.type === "error") patch((m) => void (m.error = event.message));
        },
        abort.current.signal,
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        patch((m) => void (m.error = error instanceof Error ? error.message : "The request failed."));
      }
    } finally {
      patch((m) => void (m.pending = false));
      setBusy(false);
    }
  }

  function restart() {
    abort.current?.abort();
    void resetChat(props.scriptId, session.current);
    session.current = crypto.randomUUID();
    setMessages([]);
    setBusy(false);
    input.current?.focus();
  }

  return (
    <aside className="chat" aria-label="Script assistant">
      <header className="chat-head">
        <div>
          <h2>Ask the script</h2>
          <p>{props.title}</p>
        </div>
        <div className="chat-actions">
          {messages.length > 0 && (
            <button className="ghost small" onClick={restart}>
              New chat
            </button>
          )}
          <button className="ghost small" onClick={props.onClose} aria-label="Close the assistant">
            Close
          </button>
        </div>
      </header>

      <div className="chat-body">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>
              The assistant reads the parsed script with tools, so its counts and page lengths are the same ones you see in the
              breakdown.
            </p>
            {available ? (
              <ul>
                {SUGGESTIONS.map((s) => (
                  <li key={s}>
                    <button className="suggestion" onClick={() => void send(s)}>
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="notice">{props.status?.llm.reason || "The AI features are not available."}</p>
            )}
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div className="bubble user" key={i}>
              {m.text}
            </div>
          ) : (
            <div className="bubble assistant" key={i}>
              {m.steps.length > 0 && (
                <ul className="steps">
                  {m.steps.map((step, k) => (
                    <li key={k}>{describeStep(step)}</li>
                  ))}
                </ul>
              )}
              <Markdown text={m.text.trim()} />
              {m.pending && !m.text.trim() && <p className="thinking">{m.steps.length ? "Reading…" : "Thinking…"}</p>}
              {m.error && <p className="notice error">{m.error}</p>}
            </div>
          ),
        )}
        <div ref={end} />
      </div>

      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          void send(draft);
        }}
      >
        <textarea
          ref={input}
          value={draft}
          rows={2}
          placeholder={available ? "Ask about scenes, characters, schedule…" : "AI features are off"}
          disabled={!available}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void send(draft);
            }
          }}
        />
        <button className="primary" type="submit" disabled={!available || busy || !draft.trim()}>
          {busy ? "Answering…" : "Ask"}
        </button>
      </form>
    </aside>
  );
}
