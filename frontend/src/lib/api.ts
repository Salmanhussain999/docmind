export type DocumentStatus = "processing" | "ready" | "failed";

export interface DocumentInfo {
  id: string;
  name: string;
  media_type: string;
  size_bytes: number;
  page_count: number;
  chunk_count: number;
  status: DocumentStatus;
  error: string | null;
  created_at: string;
}

export interface Source {
  number: number;
  chunk_id: number;
  document_id: string;
  document_name: string;
  page: number;
  text: string;
  score: number;
}

export interface Health {
  status: "ok";
  answer_mode: "llm" | "extractive";
  model: string;
  embeddings: string;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function errorFrom(res: Response): Promise<ApiError> {
  const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
  const detail = typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`;
  return new ApiError(res.status, detail);
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, "Can't reach the DocMind server. Is it running?");
  }
  if (!res.ok) throw await errorFrom(res);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  health: () => json<Health>("/health"),
  documents: () => json<DocumentInfo[]>("/documents"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return json<DocumentInfo>("/documents", { method: "POST", body: form });
  },
  remove: (id: string) => json<void>(`/documents/${id}`, { method: "DELETE" }),
  fileUrl: (id: string, page?: number) => `/api/documents/${id}/file${page ? `#page=${page}` : ""}`,
};

export interface StreamHandlers {
  onSources: (sources: Source[]) => void;
  onToken: (text: string) => void;
  onError: (message: string) => void;
}

/**
 * POSTs a question and reads the Server-Sent Events stream. EventSource only does GET,
 * so this parses the stream by hand: events are separated by a blank line.
 */
export async function streamAnswer(
  body: { question: string; document_ids: string[]; history: ChatTurn[] },
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (signal.aborted) return;
    throw new ApiError(0, "Can't reach the DocMind server. Is it running?");
  }
  if (!res.ok || !res.body) throw await errorFrom(res);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const event = /^event: (.+)$/m.exec(raw)?.[1];
        const data = /^data: (.*)$/m.exec(raw)?.[1];
        if (!event || data === undefined) continue;
        const payload: unknown = JSON.parse(data);
        if (event === "sources") handlers.onSources(payload as Source[]);
        else if (event === "token") handlers.onToken((payload as { text: string }).text);
        else if (event === "error") handlers.onError((payload as { message: string }).message);
      }
    }
  } catch (err) {
    if (!signal.aborted) throw err;
  }
}
