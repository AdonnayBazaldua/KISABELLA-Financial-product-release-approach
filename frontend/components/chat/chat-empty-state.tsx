// frontend/components/chat/chat-empty-state.tsx
export function ChatEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-slate-400">
      <p className="text-sm">Haz tu primera pregunta sobre esta evaluación</p>
      <p className="text-xs mt-1">Puedes adjuntar cotizaciones, análisis o listas de precios</p>
    </div>
  );
}
