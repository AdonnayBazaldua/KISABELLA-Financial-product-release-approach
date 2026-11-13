import { notFound } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Scorecard } from "@/components/scorecard";
import { ChatPanel } from "@/components/chat/chat-panel";

async function getChatMessages(evalId: string) {
  try {
    const base = process.env.API_URL_INTERNAL ?? process.env.NEXT_PUBLIC_API_URL ?? "";
    const res = await fetch(
      `${base}/api/v1/evaluations/${evalId}/chat/messages`,
      { cache: "no-store" }
    );
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function EvaluationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let evaluation;
  try {
    evaluation = await api.getEvaluation(id);
  } catch {
    notFound();
  }

  const messages = await getChatMessages(id);

  return (
    <div className="max-w-3xl mx-auto px-4">
      <div className="pt-4 pb-2">
        <Link href="/dashboard" className="text-sm text-slate-500 hover:text-slate-800">
          ← Volver al dashboard
        </Link>
      </div>
      <Scorecard evaluation={evaluation} />
      <div className="mt-8 mb-8">
        <ChatPanel evalId={id} initialMessages={messages} />
      </div>
    </div>
  );
}
