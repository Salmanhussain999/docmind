import { useEffect, useRef } from "react";
import { ArrowUpRight, X } from "lucide-react";
import { api, type Source } from "../lib/api";
import { highlightSentences } from "../lib/text";

interface SourcesProps {
  question: string;
  sources: Source[];
  active: number | null;
  onSelect: (n: number) => void;
  onClose?: () => void;
}

/** The evidence behind an answer: each numbered passage with its document, page and best-matching lines marked. */
export function Sources({ question, sources, active, onSelect, onClose }: SourcesProps) {
  const refs = useRef(new Map<number, HTMLElement>());

  useEffect(() => {
    if (active !== null) refs.current.get(active)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [active]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">Sources</h2>
          <p className="mt-0.5 line-clamp-2 text-xs text-ink-soft">For “{question}”</p>
        </div>
        {onClose && (
          <button onClick={onClose} className="rounded p-1 text-ink-faint hover:bg-shelf hover:text-ink" aria-label="Close sources">
            <X className="size-4" />
          </button>
        )}
      </div>

      {sources.length === 0 ? (
        <p className="px-5 py-6 text-sm text-ink-soft">No passages matched this question.</p>
      ) : (
        <ol className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
          {sources.map((s) => {
            const isActive = active === s.number;
            return (
              <li
                key={s.chunk_id}
                ref={(el) => {
                  if (el) refs.current.set(s.number, el);
                  else refs.current.delete(s.number);
                }}
              >
                <article
                  onClick={() => onSelect(s.number)}
                  className={`cursor-pointer rounded-lg border p-4 transition-colors ${
                    isActive ? "border-marker-edge bg-marker-wash" : "border-line bg-paper hover:border-ink-faint/50"
                  }`}
                  aria-current={isActive || undefined}
                >
                  <header className="flex items-center gap-2.5 text-xs">
                    <span
                      className={`inline-flex size-5 shrink-0 items-center justify-center rounded font-semibold tabular-nums ${
                        isActive ? "bg-marker text-ink" : "bg-shelf text-ink-soft"
                      }`}
                    >
                      {s.number}
                    </span>
                    <span className="min-w-0 flex-1 truncate font-medium" title={s.document_name}>
                      {s.document_name}
                    </span>
                    <a
                      href={api.fileUrl(s.document_id, s.page)}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex shrink-0 items-center gap-0.5 text-ink-soft hover:text-ink hover:underline"
                    >
                      Page {s.page}
                      <ArrowUpRight className="size-3" aria-hidden />
                    </a>
                  </header>
                  <p className="mt-2.5 font-serif text-[15px] leading-relaxed text-ink-soft">
                    {highlightSentences(s.text, question).map((part, i) =>
                      part.heading ? (
                        <span key={i} className="mb-1 block font-sans text-xs font-semibold text-ink">
                          {part.text}
                        </span>
                      ) : (
                        <span key={i}>
                          {i > 0 && " "}
                          {part.hit ? <mark className="highlight text-ink">{part.text}</mark> : part.text}
                        </span>
                      ),
                    )}
                  </p>
                </article>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
