import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">
          Página no encontrada
        </h1>
        <p className="text-slate-600 mb-6">
          La página que buscás no existe o fue movida.
        </p>
        <Link
          href="/dashboard"
          className="bg-slate-900 text-white px-4 py-2 rounded-lg hover:bg-slate-700 transition-colors inline-block"
        >
          Volver al dashboard
        </Link>
      </div>
    </div>
  );
}
