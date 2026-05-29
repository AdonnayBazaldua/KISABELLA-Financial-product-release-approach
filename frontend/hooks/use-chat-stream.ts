// frontend/hooks/use-chat-stream.ts
"use client";

import { useCallback, useRef, useState } from "react";

export type ChatStreamStatus = "idle" | "sending" | "streaming" | "complete" | "error";

export interface StreamedMessage {
  messageId: string;
  content: string;
}

export function useChatStream(evalId: string) {
  const [status, setStatus] = useState<ChatStreamStatus>("idle");
  const [streamingContent, setStreamingContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const send = useCallback(
    async (content: string, files: File[]): Promise<StreamedMessage | null> => {
      if (status === "sending" || status === "streaming") return null;

      setStatus("sending");
      setStreamingContent("");
      setError(null);

      // Build form data
      const form = new FormData();
      form.append("content", content);
      for (const f of files) {
        form.append("files", f);
      }

      // POST message
      let messageId: string;
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";
        const res = await fetch(
          `${apiBase}/api/v1/evaluations/${evalId}/chat/messages`,
          { method: "POST", body: form }
        );
        if (!res.ok) {
          const errData = await res.json().catch(() => ({})) as { detail?: string };
          throw new Error(errData.detail ?? `Error ${res.status}`);
        }
        const data = await res.json() as { message_id: string; status: string };
        messageId = data.message_id;
      } catch (e) {
        setStatus("error");
        setError(e instanceof Error ? e.message : "Error al enviar mensaje");
        return null;
      }

      // Open SSE stream
      setStatus("streaming");

      return new Promise<StreamedMessage | null>((resolve, reject) => {
        const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "";
        const es = new EventSource(
          `${apiBase}/api/v1/evaluations/${evalId}/chat/messages/${messageId}/stream`
        );
        esRef.current = es;
        let accumulated = "";

        es.addEventListener("token", (e: MessageEvent) => {
          const data = JSON.parse(e.data) as { token: string };
          accumulated += data.token;
          setStreamingContent(accumulated);
        });

        es.addEventListener("complete", (e: MessageEvent) => {
          const data = JSON.parse(e.data) as { message_id: string; content: string };
          es.close();
          esRef.current = null;
          setStreamingContent("");
          setStatus("complete");
          resolve({ messageId: data.message_id, content: data.content });
        });

        es.addEventListener("error", (e: Event) => {
          es.close();
          esRef.current = null;
          setStatus("error");
          const msg = (e as MessageEvent).data
            ? (JSON.parse((e as MessageEvent).data) as { error?: string }).error ?? "Error en el stream"
            : "Error en el stream";
          setError(msg);
          reject(new Error(msg));
        });

        es.onerror = () => {
          if (es.readyState === EventSource.CLOSED) {
            esRef.current = null;
            setStatus("error");
            setError("Conexión perdida");
            reject(new Error("Connection closed"));
          }
        };
      });
    },
    [evalId, status]
  );

  const reset = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setStatus("idle");
    setStreamingContent("");
    setError(null);
  }, []);

  return { send, status, streamingContent, error, reset };
}
