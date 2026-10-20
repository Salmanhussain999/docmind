import { memo } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { linkCitations } from "../lib/text";
import type { Source } from "../lib/api";

interface AnswerProps {
  content: string;
  sources: Source[];
  streaming: boolean;
  activeCitation: number | null;
  onCite: (n: number) => void;
}

/** Renders the model's markdown, drawing each [n] citation as a highlighter mark that opens its source. */
export const Answer = memo(function Answer({ content, sources, streaming, activeCitation, onCite }: AnswerProps) {
  return (
    <div className={`answer font-serif text-[17px] leading-relaxed text-ink ${streaming ? "streaming-caret" : ""}`}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const match = href?.match(/^#cite-(\d+)$/);
            if (!match) {
              return (
                <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                  {children}
                </a>
              );
            }
            const n = Number(match[1]);
            const source = sources.find((s) => s.number === n);
            if (!source) return <span className="text-ink-faint">[{n}]</span>;
            return (
              <button
                type="button"
                onClick={() => onCite(n)}
                aria-label={`Source ${n}: ${source.document_name}, page ${source.page}`}
                aria-pressed={activeCitation === n}
                className={`highlight mx-px cursor-pointer align-baseline font-sans text-[12px] font-semibold tabular-nums text-ink hover:[--color-marker:var(--color-marker-edge)] ${
                  activeCitation === n ? "[--color-marker:var(--color-marker-edge)]" : ""
                }`}
              >
                {n}
              </button>
            );
          },
        }}
      >
        {linkCitations(content)}
      </Markdown>
    </div>
  );
});
