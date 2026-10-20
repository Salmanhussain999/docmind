import { useCallback, useRef, useState } from "react";
import { streamAnswer, type ChatTurn, type Source } from "../lib/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  question?: string; // for answers: the question they respond to
  sources?: Source[];
  status: "streaming" | "done" | "error" | "stopped";
  error?: string;
}

let counter = 0;
const nextId = () => `m${Date.now()}-${counter++}`;

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const controller = useRef<AbortController | null>(null);
  const streaming = messages.at(-1)?.status === "streaming";

  const patch = (id: string, update: (m: Message) => Partial<Message>) =>
    setMessages((all) => all.map((m) => (m.id === id ? { ...m, ...update(m) } : m)));

  const ask = useCallback(
    async (question: string, documentIds: string[]) => {
      // Earlier completed turns give the model context for follow-up questions.
      const history: ChatTurn[] = messages
        .filter((m) => m.status === "done" && m.content)
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.content }));

      const answerId = nextId();
      setMessages((all) => [
        ...all,
        { id: nextId(), role: "user", content: question, status: "done" },
        { id: answerId, role: "assistant", content: "", question, status: "streaming" },
      ]);

      const abort = new AbortController();
      controller.current = abort;
      try {
        await streamAnswer(
          { question, document_ids: documentIds, history },
          {
            onSources: (sources) => patch(answerId, () => ({ sources })),
            onToken: (text) => patch(answerId, (m) => ({ content: m.content + text })),
            onError: (error) => patch(answerId, () => ({ status: "error", error })),
          },
          abort.signal,
        );
        patch(answerId, (m) => ({ status: abort.signal.aborted ? "stopped" : m.status === "error" ? "error" : "done" }));
      } catch (err) {
        patch(answerId, () => ({ status: "error", error: err instanceof Error ? err.message : "Something went wrong" }));
      } finally {
        controller.current = null;
      }
    },
    [messages],
  );

  const stop = useCallback(() => controller.current?.abort(), []);
  const reset = useCallback(() => {
    controller.current?.abort();
    setMessages([]);
  }, []);

  return { messages, streaming, ask, stop, reset };
}
