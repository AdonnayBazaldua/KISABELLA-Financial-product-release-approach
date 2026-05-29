// frontend/components/chat/chat-message.tsx
"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Attachment {
  id: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
}

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  status: "complete" | "streaming" | "error";
  attachments?: Attachment[];
}

export function ChatMessage({ role, content, status, attachments = [] }: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-slate-100 text-slate-800"
        }`}
      >
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {attachments.map((a) => (
              <span
                key={a.id}
                className={`text-xs px-2 py-0.5 rounded-full ${
                  isUser ? "bg-blue-500 text-blue-100" : "bg-slate-200 text-slate-600"
                }`}
              >
                {a.original_name}
              </span>
            ))}
          </div>
        )}

        {status === "error" ? (
          <p className="text-red-500 text-xs italic">Error al generar respuesta</p>
        ) : isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="prose prose-sm max-w-none prose-slate">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            {status === "streaming" && (
              <span className="inline-block w-1.5 h-4 bg-slate-400 animate-pulse ml-0.5 align-middle" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
