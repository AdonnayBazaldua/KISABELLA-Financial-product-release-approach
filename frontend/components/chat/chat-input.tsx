// frontend/components/chat/chat-input.tsx
"use client";

import { useRef, useState } from "react";
import { AttachmentChip } from "./attachment-chip";
import { useFileValidation } from "@/hooks/use-file-validation";
import type { ChatStreamStatus } from "@/hooks/use-chat-stream";

interface ChatInputProps {
  onSend: (content: string, files: File[]) => void;
  status: ChatStreamStatus;
}

export function ChatInput({ onSend, status }: ChatInputProps) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [fileErrors, setFileErrors] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);
  const { validate, MAX_FILES } = useFileValidation();

  const isDisabled = status === "sending" || status === "streaming";

  function handleFiles(incoming: FileList | null) {
    if (!incoming) return;
    const { valid, errors } = validate([...files, ...Array.from(incoming)]);
    setFiles(valid);
    setFileErrors(errors.map((e) => `${e.file.name}: ${e.reason}`));
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() && files.length === 0) return;
    onSend(text.trim(), files);
    setText("");
    setFiles([]);
    setFileErrors([]);
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-slate-200 p-4">
      {fileErrors.length > 0 && (
        <div className="mb-2 text-xs text-red-600 space-y-0.5">
          {fileErrors.map((e, i) => (
            <p key={i}>{e}</p>
          ))}
        </div>
      )}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {files.map((f, i) => (
            <AttachmentChip
              key={i}
              name={f.name}
              sizeBytes={f.size}
              onRemove={() => removeFile(i)}
            />
          ))}
        </div>
      )}
      <div className="flex gap-2 items-end">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e as unknown as React.FormEvent);
            }
          }}
          placeholder="Escribe tu pregunta... (Enter para enviar, Shift+Enter para nueva línea)"
          disabled={isDisabled}
          rows={2}
          className="flex-1 resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50
                     placeholder:text-slate-400"
        />
        <button
          type="button"
          disabled={isDisabled || files.length >= MAX_FILES}
          onClick={() => fileRef.current?.click()}
          title="Adjuntar archivo (máx 3)"
          className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 disabled:opacity-40 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
          </svg>
        </button>
        <button
          type="submit"
          disabled={isDisabled || (!text.trim() && files.length === 0)}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium
                     hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {isDisabled ? (
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ...
            </span>
          ) : "Enviar"}
        </button>
      </div>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".pdf,.docx,.xlsx,.csv,.txt,.jpg,.jpeg,.png,.webp"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </form>
  );
}
