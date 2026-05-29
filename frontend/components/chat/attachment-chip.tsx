// frontend/components/chat/attachment-chip.tsx
interface AttachmentChipProps {
  name: string;
  sizeBytes: number;
  onRemove: () => void;
}

export function AttachmentChip({ name, sizeBytes, onRemove }: AttachmentChipProps) {
  const sizeLabel =
    sizeBytes > 1024 * 1024
      ? `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`
      : `${Math.round(sizeBytes / 1024)} KB`;

  return (
    <div className="inline-flex items-center gap-1.5 bg-slate-100 rounded-full px-3 py-1 text-xs text-slate-700">
      <span className="max-w-[120px] truncate">{name}</span>
      <span className="text-slate-400">{sizeLabel}</span>
      <button
        type="button"
        onClick={onRemove}
        className="ml-1 text-slate-400 hover:text-red-500 transition-colors"
        aria-label={`Eliminar ${name}`}
      >
        ×
      </button>
    </div>
  );
}
