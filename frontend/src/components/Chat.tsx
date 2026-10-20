import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { AlertCircle, ArrowUp, RotateCcw, Square } from "lucide-react";
import type { Message } from "../hooks/useChat";
import { Answer } from "./Answer";

interface ChatProps {
  messages: Message[];
  streaming: boolean;
  canAsk: boolean;
  readyCount: number;
  processing: boolean;
  activeAnswerId: string | null;
  activeCitation: number | null;
  onAsk: (question: string) => void;
  onStop: () => void;
  onReset: () => void;
  onCite: (answerId: string, n: number) => void;
  onShowSources: (answerId: string) => void;
  onPickFiles: () => void;
}

const SUGGESTIONS = ["Summarise the key points", "What deadlines or dates are mentioned?", "List any amounts or limits"];

export function Chat(props: ChatProps) {
  const { messages, streaming, canAsk, readyCount, processing, onAsk, onStop, onReset } = props;
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const lastContent = messages.at(-1)?.content;

  // Follow the answer as it streams in.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, lastContent]);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const question = draft.trim();
    if (!question || !canAsk || streaming) return;
    onAsk(question);
    setDraft("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[44rem] px-5 py-8 sm:px-8">
          {messages.length === 0 ? (
            readyCount === 0 ? (
              <Welcome processing={processing} onPickFiles={props.onPickFiles} />
            ) : (
              <div className="pt-[12vh]">
                <h1 className="font-serif text-3xl font-semibold tracking-tight sm:text-4xl">
                  Ask about {readyCount === 1 ? "your document" : `your ${readyCount} documents`}
                </h1>
                <p className="mt-3 text-ink-soft">Every answer points to the page it came from, so you can check it.</p>
                <div className="mt-8 flex flex-wrap gap-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => onAsk(s)}
                      className="rounded-full border border-line px-3.5 py-1.5 text-sm text-ink-soft hover:border-ink-faint hover:text-ink"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )
          ) : (
            <ol className="space-y-8" aria-live="polite" aria-busy={streaming}>
              {messages.map((m) =>
                m.role === "user" ? (
                  <li key={m.id} className="flex justify-end">
                    <p className="max-w-[85%] rounded-2xl rounded-br-md bg-shelf px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap">
                      {m.content}
                    </p>
                  </li>
                ) : (
                  <li key={m.id}>
                    <AnswerBlock message={m} {...props} />
                  </li>
                ),
              )}
            </ol>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <div className="border-t border-line bg-paper px-4 pt-3 pb-4 sm:px-8">
        <form onSubmit={submit} className="mx-auto flex w-full max-w-[44rem] items-end gap-2">
          {messages.length > 0 && !streaming && (
            <button
              type="button"
              onClick={() => {
                onReset();
                inputRef.current?.focus();
              }}
              className="mb-1 rounded-lg p-2 text-ink-faint hover:bg-shelf hover:text-ink"
              aria-label="Start a new conversation"
              title="New conversation"
            >
              <RotateCcw className="size-4" />
            </button>
          )}
          <label htmlFor="question" className="sr-only">
            Question
          </label>
          <textarea
            id="question"
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            maxLength={2000}
            disabled={!canAsk}
            placeholder={canAsk ? "Ask a question about your documents" : "Add a document to start asking questions"}
            className="max-h-40 min-h-11 flex-1 resize-none rounded-xl border border-line bg-paper px-4 py-2.5 text-[15px] leading-relaxed placeholder:text-ink-faint focus:border-ink-faint focus:outline-none disabled:bg-shelf [field-sizing:content]"
          />
          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              className="mb-0.5 inline-flex size-10 items-center justify-center rounded-full border border-line text-ink hover:bg-shelf"
              aria-label="Stop answering"
            >
              <Square className="size-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!draft.trim() || !canAsk}
              className="mb-0.5 inline-flex size-10 items-center justify-center rounded-full bg-ink text-white hover:bg-ink/90 disabled:bg-line disabled:text-ink-faint"
              aria-label="Ask"
            >
              <ArrowUp className="size-4" />
            </button>
          )}
        </form>
      </div>
    </div>
  );
}

function AnswerBlock({ message: m, activeAnswerId, activeCitation, onCite, onShowSources }: { message: Message } & ChatProps) {
  const sources = m.sources ?? [];
  const isActive = activeAnswerId === m.id;
  const waiting = m.status === "streaming" && !m.content;

  return (
    <div>
      {waiting ? (
        <p className="flex items-center gap-2 text-sm text-ink-soft" role="status">
          <span className="size-3 animate-spin rounded-full border-2 border-ink-faint border-r-transparent" aria-hidden />
          {sources.length ? `Reading ${sources.length} passages…` : "Searching your documents…"}
        </p>
      ) : (
        m.content && (
          <Answer
            content={m.content}
            sources={sources}
            streaming={m.status === "streaming"}
            activeCitation={isActive ? activeCitation : null}
            onCite={(n) => onCite(m.id, n)}
          />
        )
      )}

      {m.status === "error" && (
        <p className="mt-3 flex gap-2 rounded-lg bg-danger/8 px-3 py-2 text-sm text-danger" role="alert">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {m.error}
        </p>
      )}
      {m.status === "stopped" && <p className="mt-2 text-xs text-ink-faint">Stopped.</p>}

      {sources.length > 0 && m.status !== "streaming" && (
        <button
          onClick={() => onShowSources(m.id)}
          className={`mt-4 inline-flex items-center gap-2 rounded-md text-xs ${isActive ? "text-ink" : "text-ink-soft hover:text-ink"}`}
        >
          <span className="flex -space-x-1">
            {sources.slice(0, 4).map((s) => (
              <span key={s.number} className="inline-flex size-4.5 items-center justify-center rounded bg-marker text-[10px] font-semibold ring-2 ring-paper">
                {s.number}
              </span>
            ))}
          </span>
          {sources.length} sources from {new Set(sources.map((s) => s.document_name)).size === 1 ? sources[0]?.document_name : `${new Set(sources.map((s) => s.document_id)).size} documents`}
        </button>
      )}
    </div>
  );
}

function Welcome({ processing, onPickFiles }: { processing: boolean; onPickFiles: () => void }) {
  return (
    <div className="pt-[8vh]">
      <h1 className="font-serif text-4xl leading-tight font-semibold tracking-tight sm:text-5xl">
        Ask your documents, and see where every answer comes from.
      </h1>
      <p className="mt-4 max-w-lg text-lg text-ink-soft">
        Add a PDF and ask it questions. DocMind finds the passages that answer you and cites the page for every claim.
      </p>
      <button
        onClick={onPickFiles}
        className="mt-10 flex w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line px-6 py-12 text-center hover:border-ink-faint"
      >
        {processing ? (
          <span className="inline-flex items-center gap-2 text-ink-soft">
            <span className="size-4 animate-spin rounded-full border-2 border-ink-faint border-r-transparent" aria-hidden />
            Reading your document…
          </span>
        ) : (
          <>
            <span className="font-medium">Drop a file here, or click to choose</span>
            <span className="text-sm text-ink-faint">PDF, TXT or Markdown. Files stay on this server.</span>
          </>
        )}
      </button>
    </div>
  );
}
