// frontend/hooks/use-file-validation.ts
"use client";

const ALLOWED_MIMES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/csv",
  "text/plain",
  "image/jpeg",
  "image/png",
  "image/webp",
]);

const MAX_FILE_BYTES = 5 * 1024 * 1024; // 5MB
const MAX_FILES = 3;

export interface FileValidationError {
  file: File;
  reason: string;
}

export function useFileValidation() {
  function validate(files: File[]): { valid: File[]; errors: FileValidationError[] } {
    const valid: File[] = [];
    const errors: FileValidationError[] = [];

    for (const f of files) {
      if (!ALLOWED_MIMES.has(f.type)) {
        errors.push({ file: f, reason: `Tipo no permitido: ${f.type || "desconocido"}` });
        continue;
      }
      if (f.size > MAX_FILE_BYTES) {
        errors.push({ file: f, reason: `Excede 5MB (${(f.size / 1024 / 1024).toFixed(1)}MB)` });
        continue;
      }
      valid.push(f);
    }

    // Cap at MAX_FILES
    if (valid.length > MAX_FILES) {
      const extra = valid.splice(MAX_FILES);
      for (const f of extra) {
        errors.push({ file: f, reason: "Máximo 3 archivos por mensaje" });
      }
    }

    return { valid, errors };
  }

  return { validate, MAX_FILES, MAX_FILE_BYTES };
}
