import { useRef, useState } from "react";
import { AlertCircle, ExternalLink, FilePlus2, Trash2 } from "lucide-react";
import { api, type DocumentInfo, type Health } from "../lib/api";
import { formatBytes } from "../lib/text";
import { Logo } from "./Logo";

interface LibraryProps {
  documents: DocumentInfo[];
  loading: boolean;
  selected: Set<string>;
  onToggle: (id: string) => void;
  onUpload: (files: File[]) => void;
  onDelete: (id: string) => void;
  uploading: boolean;
  health?: Health;
}

export const ACCEPT = ".pdf,.txt,.md";

export function Library({ documents, loading, selected, onToggle, onUpload, onDelete, uploading, health }: LibraryProps) {
  const input = useRef<HTMLInputElement>(null);
  const ready = documents.filter((d) => d.status === "ready");

  return (
    <div className="flex h-full flex-col">
      <div className="px-5 pt-5 pb-4">
        <Logo />
      </div>

      <div className="px-4">
        <button
          onClick={() => input.current?.click()}
          disabled={uploading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-3 py-2.5 text-sm font-medium text-white hover:bg-ink/90 disabled:opacity-60"
        >
          <FilePlus2 className="size-4" aria-hidden />
          {uploading ? "Uploading…" : "Add documents"}
        </button>
        <input
          ref={input}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={(e) => {
            onUpload(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
        <p className="mt-2 text-center text-xs text-ink-faint">PDF, TXT or Markdown, up to 20 MB</p>
      </div>

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto px-2">
        <div className="mb-1 flex items-baseline justify-between px-3">
          <h2 className="text-xs font-semibold text-ink-soft">Library</h2>
          {ready.length > 1 && (
            <span className="text-xs text-ink-faint">
              {selected.size === ready.length ? "Searching all" : `Searching ${selected.size} of ${ready.length}`}
            </span>
          )}
        </div>

        {loading ? (
          <div className="space-y-2 px-3 pt-2">
            {[0, 1].map((i) => (
              <div key={i} className="h-11 animate-pulse rounded-md bg-line/60" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <p className="px-3 py-2 text-sm text-ink-faint">Documents you add appear here.</p>
        ) : (
          <ul className="space-y-0.5">
            {documents.map((doc) => (
              <DocumentRow
                key={doc.id}
                doc={doc}
                checked={selected.has(doc.id)}
                onToggle={() => onToggle(doc.id)}
                onDelete={() => onDelete(doc.id)}
              />
            ))}
          </ul>
        )}
      </div>

      {health && (
        <div className="border-t border-line px-5 py-3 text-xs text-ink-soft">
          {health.answer_mode === "llm" ? (
            <p>
              Answers written by <span className="font-medium text-ink">{health.model}</span>
            </p>
          ) : (
            <p>
              <span className="font-medium text-ink">Quote mode.</span> No AI model is connected, so answers quote the
              most relevant sentences.{" "}
              <a
                href="https://github.com/Salmanhussain999/docmind#connect-an-ai-model"
                target="_blank"
                rel="noreferrer"
                className="underline decoration-ink-faint underline-offset-2 hover:text-ink"
              >
                Connect a model
              </a>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function DocumentRow({
  doc,
  checked,
  onToggle,
  onDelete,
}: {
  doc: DocumentInfo;
  checked: boolean;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const id = `doc-${doc.id}`;

  return (
    <li className="group rounded-md px-3 py-2 hover:bg-white">
      <div className="flex items-start gap-2.5">
        <input
          id={id}
          type="checkbox"
          checked={doc.status === "ready" && checked}
          disabled={doc.status !== "ready"}
          onChange={onToggle}
          className="mt-0.5 size-4 shrink-0 accent-ink disabled:opacity-40"
          aria-describedby={`${id}-meta`}
        />
        <div className="min-w-0 flex-1">
          <label htmlFor={id} className="block truncate text-sm font-medium" title={doc.name}>
            {doc.name}
          </label>
          <p id={`${id}-meta`} className="mt-0.5 text-xs text-ink-faint">
            {doc.status === "processing" && (
              <span className="inline-flex items-center gap-1.5 text-ink-soft">
                <span className="size-3 animate-spin rounded-full border-2 border-ink-faint border-r-transparent" aria-hidden />
                Reading…
              </span>
            )}
            {doc.status === "ready" &&
              `${doc.page_count} ${doc.page_count === 1 ? "page" : "pages"}, ${formatBytes(doc.size_bytes)}`}
          </p>
          {doc.status === "failed" && (
            <p className="mt-1 flex gap-1.5 text-xs text-danger">
              <AlertCircle className="mt-px size-3.5 shrink-0" aria-hidden />
              {doc.error}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center opacity-100 transition-opacity sm:opacity-0 sm:group-focus-within:opacity-100 sm:group-hover:opacity-100">
          {doc.status === "ready" && (
            <a
              href={api.fileUrl(doc.id)}
              target="_blank"
              rel="noreferrer"
              className="rounded p-1 text-ink-faint hover:text-ink"
              aria-label={`Open ${doc.name}`}
              title="Open original"
            >
              <ExternalLink className="size-3.5" />
            </a>
          )}
          <button
            onClick={() => setConfirming(true)}
            className="rounded p-1 text-ink-faint hover:text-danger"
            aria-label={`Remove ${doc.name}`}
            title="Remove"
          >
            <Trash2 className="size-3.5" />
          </button>
        </div>
      </div>
      {confirming && (
        <div className="mt-2 flex items-center justify-end gap-2 text-xs" role="group" aria-label="Confirm removal">
          <span className="mr-auto text-ink-soft">Remove from library?</span>
          <button onClick={() => setConfirming(false)} className="rounded px-2 py-1 hover:bg-shelf">
            Keep
          </button>
          <button onClick={onDelete} className="rounded bg-danger px-2 py-1 font-medium text-white">
            Remove
          </button>
        </div>
      )}
    </li>
  );
}
