import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Menu, X } from "lucide-react";
import { useDeleteDocument, useDocuments, useHealth, useUpload } from "./hooks/useDocuments";
import { useChat } from "./hooks/useChat";
import { ACCEPT, Library } from "./components/Library";
import { Chat } from "./components/Chat";
import { Sources } from "./components/Sources";
import { Logo } from "./components/Logo";

export function App() {
  const { data: documents = [], isLoading } = useDocuments();
  const { data: health } = useHealth();
  const upload = useUpload();
  const remove = useDeleteDocument();
  const chat = useChat();

  const [deselected, setDeselected] = useState<Set<string>>(new Set());
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false); // below the xl breakpoint
  const [active, setActive] = useState<{ answerId: string | null; citation: number | null }>({ answerId: null, citation: null });
  const [dragging, setDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string>();
  const fileInput = useRef<HTMLInputElement>(null);

  const ready = useMemo(() => documents.filter((d) => d.status === "ready"), [documents]);
  // Everything is selected unless the user unticked it, so new uploads are searched straight away.
  const selected = useMemo(() => new Set(ready.filter((d) => !deselected.has(d.id)).map((d) => d.id)), [ready, deselected]);
  const processing = documents.some((d) => d.status === "processing");

  const answers = chat.messages.filter((m) => m.role === "assistant");
  const shownAnswer = answers.find((m) => m.id === active.answerId) ?? answers.at(-1);

  // A new question moves the sources panel to the new answer.
  const latestId = answers.at(-1)?.id ?? null;
  useEffect(() => setActive({ answerId: latestId, citation: null }), [latestId]);

  const uploadFiles = useCallback(
    async (files: File[]) => {
      setUploadError(undefined);
      for (const file of files) {
        try {
          await upload.mutateAsync(file);
        } catch (err) {
          setUploadError(`${file.name}: ${err instanceof Error ? err.message : "upload failed"}`);
        }
      }
    },
    [upload],
  );

  // Drop files anywhere on the window.
  useEffect(() => {
    let depth = 0;
    const hasFiles = (e: DragEvent) => e.dataTransfer?.types.includes("Files");
    const enter = (e: DragEvent) => hasFiles(e) && (depth++, setDragging(true));
    const leave = (e: DragEvent) => hasFiles(e) && --depth <= 0 && ((depth = 0), setDragging(false));
    const over = (e: DragEvent) => hasFiles(e) && e.preventDefault();
    const drop = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth = 0;
      setDragging(false);
      void uploadFiles(Array.from(e.dataTransfer?.files ?? []));
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
    };
  }, [uploadFiles]);

  const toggle = (id: string) =>
    setDeselected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const cite = (answerId: string, citation: number) => {
    setActive({ answerId, citation });
    setSourcesOpen(true);
  };

  const library = (
    <Library
      documents={documents}
      loading={isLoading}
      selected={selected}
      onToggle={toggle}
      onUpload={uploadFiles}
      onDelete={(id) => remove.mutate(id)}
      uploading={upload.isPending}
      health={health}
    />
  );

  const sourcesPanel = shownAnswer?.sources && shownAnswer.question && (
    <Sources
      question={shownAnswer.question}
      sources={shownAnswer.sources}
      active={active.answerId === shownAnswer.id ? active.citation : null}
      onSelect={(n) => setActive({ answerId: shownAnswer.id, citation: n })}
      onClose={() => setSourcesOpen(false)}
    />
  );

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside className="hidden w-72 shrink-0 border-r border-line bg-shelf lg:block">{library}</aside>

      {libraryOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/30" onClick={() => setLibraryOpen(false)} />
          <aside className="panel-in absolute inset-y-0 left-0 w-80 max-w-[88vw] bg-shelf shadow-xl">
            <button
              onClick={() => setLibraryOpen(false)}
              className="absolute top-4 right-3 rounded p-1.5 text-ink-soft hover:bg-white"
              aria-label="Close library"
            >
              <X className="size-4" />
            </button>
            {library}
          </aside>
        </div>
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-line px-4 py-3 lg:hidden">
          <button onClick={() => setLibraryOpen(true)} className="rounded p-1.5 text-ink-soft hover:bg-shelf" aria-label="Open library">
            <Menu className="size-5" />
          </button>
          <Logo />
          <span className="w-8" />
        </header>
        {uploadError && (
          <div className="flex items-start justify-between gap-3 border-b border-danger/20 bg-danger/5 px-5 py-2.5 text-sm text-danger" role="alert">
            {uploadError}
            <button onClick={() => setUploadError(undefined)} aria-label="Dismiss">
              <X className="size-4" />
            </button>
          </div>
        )}
        <Chat
          messages={chat.messages}
          streaming={chat.streaming}
          canAsk={selected.size > 0}
          readyCount={ready.length}
          processing={processing}
          activeAnswerId={active.answerId}
          activeCitation={active.citation}
          onAsk={(q) => chat.ask(q, [...selected])}
          onStop={chat.stop}
          onReset={chat.reset}
          onCite={cite}
          onShowSources={(answerId) => {
            setActive({ answerId, citation: null });
            setSourcesOpen(true);
          }}
          onPickFiles={() => fileInput.current?.click()}
        />
      </main>

      {sourcesPanel && (
        <>
          <aside className="hidden w-[25rem] shrink-0 border-l border-line xl:block">{sourcesPanel}</aside>
          {sourcesOpen && (
            <div className="fixed inset-0 z-40 xl:hidden">
              <div className="absolute inset-0 bg-ink/30" onClick={() => setSourcesOpen(false)} />
              <aside className="panel-in absolute inset-y-0 right-0 w-[26rem] max-w-[92vw] bg-paper shadow-xl">{sourcesPanel}</aside>
            </div>
          )}
        </>
      )}

      <input
        ref={fileInput}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(e) => {
          void uploadFiles(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />

      {dragging && (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-paper/85 p-6">
          <div className="rounded-2xl border-2 border-dashed border-ink px-10 py-12 text-center">
            <p className="text-lg font-semibold">Drop to add to your library</p>
            <p className="mt-1 text-sm text-ink-soft">PDF, TXT or Markdown</p>
          </div>
        </div>
      )}
    </div>
  );
}
