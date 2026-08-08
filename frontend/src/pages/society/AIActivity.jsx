import { PageHeader } from "@/components/Layout";
import { StatCard } from "@/components/StatCard";
import { useFetch } from "@/lib/useScope";
import { Loader2, Bot, EyeOff, ClipboardCheck, Copy, Activity } from "lucide-react";

const DECISION = {
  ticket_created: { label: "TICKET CREATED", cls: "text-emerald-600" },
  ignored: { label: "IGNORED", cls: "text-zinc-400" },
  review_queue: { label: "REVIEW QUEUE", cls: "text-amber-600" },
  duplicate: { label: "DUPLICATE", cls: "text-sky-600" },
};

export default function AIActivity() {
  const { data, loading } = useFetch("/society/ai/activity");
  if (loading || !data) return <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-zinc-400" /></div>;
  const { logs, stats } = data;

  return (
    <div className="p-8">
      <PageHeader title="AI Activity" subtitle="Detection Command Center" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatCard testid="ai-stat-total" label="Processed" value={stats.total} icon={Activity} />
        <StatCard testid="ai-stat-detected" label="Tickets Created" value={stats.detected} icon={Bot} accent="text-emerald-600" />
        <StatCard testid="ai-stat-review" label="Needs Review" value={stats.review} icon={ClipboardCheck} accent="text-amber-600" />
        <StatCard testid="ai-stat-dupe" label="Duplicates" value={stats.duplicate} icon={Copy} accent="text-sky-600" />
        <StatCard testid="ai-stat-ignored" label="Ignored" value={stats.ignored} icon={EyeOff} accent="text-zinc-400" />
      </div>

      <div className="mt-6 rounded-lg border border-border bg-brand-greenDark p-5">
        <p className="mb-4 font-mono text-xs uppercase tracking-[0.2em] text-brand-gold">// processing logs</p>
        <div className="max-h-[500px] space-y-2 overflow-y-auto font-mono text-xs">
          {logs.length === 0 ? <p className="text-zinc-600">No activity yet. Send a message via the WhatsApp simulator.</p> : logs.map((l) => {
            const d = DECISION[l.decision] || { label: l.decision, cls: "text-zinc-400" };
            return (
              <div key={l.id} data-testid={`ai-log-${l.id}`} className="flex flex-wrap items-start gap-2 border-b border-zinc-800/60 pb-2 text-zinc-300">
                <span className="text-zinc-600">{new Date(l.created_at).toLocaleTimeString()}</span>
                <span className={`font-semibold ${d.cls}`}>[{d.label}]</span>
                <span className="text-zinc-500">{l.phone}</span>
                <span className="flex-1 text-zinc-300">"{l.text}"</span>
                {l.confidence > 0 && <span className="text-sky-400">conf={(l.confidence * 100).toFixed(0)}%</span>}
                {l.reason && <span className="text-zinc-600">→ {l.reason}</span>}
                {l.ticket_number && <span className="text-emerald-400">{l.ticket_number}</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
