import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Kisabella Financial Product Release",
  description: "Herramienta interna de evaluación financiera",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={`${inter.className} bg-slate-50 min-h-screen`}>
        <nav className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
          <Link href="/dashboard" className="font-bold text-lg text-slate-900 tracking-tight">
            Kisabella Financial Product Release
          </Link>
          <Link
            href="/evaluations/new"
            className="bg-slate-900 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-slate-700 transition-colors"
          >
            + Nueva evaluación
          </Link>
        </nav>
        <main>{children}</main>
      </body>
    </html>
  );
}
