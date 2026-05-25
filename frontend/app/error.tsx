"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // TODO Sprint 6: enviar a Sentry / observabilidad
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">
          Algo salió mal
        </h1>
        <p className="text-slate-600 mb-6">
          Hubo un problema procesando tu solicitud. Si persiste, contactá al
          equipo.
        </p>
        {error.digest && (
          <p className="text-xs text-slate-400 mb-4">
            Código de error: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          className="bg-slate-900 text-white px-4 py-2 rounded-lg hover:bg-slate-700 transition-colors"
        >
          Reintentar
        </button>
      </div>
    </div>
  );
}
