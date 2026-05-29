// frontend/components/chat/chat-panel.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChatEmptyState } from "./chat-empty-state";
import { ChatInput } from "./chat-input";
import { ChatMessage } from "./chat-message";
import { useChatStream } from "@/hooks/use-chat-stream";

interface Attachment {
  id: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
}

interface MessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "complete" | "streaming" | "error";
  attachments?: Attachment[];
}

interface ChatPanelProps {
  evalId: string;
  initialMessages: MessageData[];
}

export function ChatPanel({ evalId, initialMessages }: ChatPanelProps) {
  const [messages, setMessages] = useState<MessageData[]>(initialMessages);
  const [pendingUserMsg, setPendingUserMsg] = useState<MessageData | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { send, status, streamingContent, error, reset } = useChatStream(evalId);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const handleSend = useCallback(
    async (content: string, files: File[]) => {
      const tempUserMsg: MessageData = {
        id: `pending-${Date.now()}`,
        role: "user",
        content,
        status: "complete",
        attachments: files.map((f, i) => ({
          id: `pending-att-${i}`,
          original_name: f.name,
          mime_type: f.type,
          size_bytes: f.size,
        })),
      };
      setPendingUserMsg(tempUserMsg);

      try {
        const result = await send(content, files);
        setPendingUserMsg(null);

        if (result) {
          setMessages((prev) => [
            ...prev,
            { ...tempUserMsg, id: `user-${Date.now()}` },
            {
              id: result.messageId,
              role: "assistant",
              content: result.content,
              status: "complete",
            },
          ]);
        }
      } catch {
        setPendingUserMsg(null);
      }
    },
    [send]
  );

  const allDisplayed = pendingUserMsg ? [...messages, pendingUserMsg] : messages;
  const showStreaming = status === "streaming" && streamingContent;

  return (
    <div className="flex flex-col border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50">
        <h3 className="text-sm font-semibold text-slate-700">Chat de seguimiento</h3>
        {status === "error" && error && (
          <button
            onClick={reset}
            className="text-xs text-slate-500 hover:text-slate-700 underline"
          >
            Reintentar
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 min-h-[200px] max-h-[500px]">
        {allDisplayed.length === 0 && !showStreaming ? (
          <ChatEmptyState />
        ) : (
          <>
            {allDisplayed.map((m) => (
              <ChatMessage
                key={m.id}
                role={m.role}
                content={m.content}
                status={m.status}
                attachments={m.attachments}
              />
            ))}
            {showStreaming && (
              <ChatMessage
                role="assistant"
                content={streamingContent}
                status="streaming"
              />
            )}
            {status === "error" && error && !showStreaming && (
              <div className="text-center py-2">
                <p className="text-xs text-red-500">{error}</p>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={handleSend} status={status} />
    </div>
  );
}
