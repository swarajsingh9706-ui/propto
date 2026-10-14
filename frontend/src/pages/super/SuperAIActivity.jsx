import { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { StatCard } from "@/components/StatCard";
import { DateRangeFilter } from "@/components/DateRangeFilter";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Bot, EyeOff, ClipboardCheck, Copy, Activity } from "lucide-react";

const DECISION = {
  ticket_created: { label: "TICKET CREATED", cls: "text-emerald-400" },
  ignored: { label: "IGNORED", cls: "text-zinc-500" },
  review_queue: { label: "REVIEW QUEUE", cls: "text-amber-400" },
  duplicate: { label: "DUPLICATE", cls: "text-sky-400" },
};

const LogRow = ({ l }) => {
  const d = DECISION[l.decision] || { label: l.decision, cls: "text-zinc-300" };
  return (
    <div data-testid={`ai-log-${l.id}`} className="flex flex-wrap items-start gap-2 border-b border-zinc-800 pb-2 text-zinc-100">
      <span className="text-zinc-500">{new Date(l.created_at).toLocaleString()}</span>
      <span className="rounded bg-indigo-500/20 px-1.5 text-indigo-300" data-testid={`ai-log-society-${l.id}`}>{l.society_name}</span>
      <span className={`font-semibold ${d.cls}`}>[{d.label}]</span>
      <span className="text-zinc-400">{l.phone}</span>
      <span className="flex-1 text-zinc-100">"{l.text}"</span>
      {l.confidence > 0 && <span className="text-sky-300">conf={(l.confidence * 100).toFixed(0)}%</span>}
      {l.reason && <span className="text-zinc-400">→ {l.reason}</span>}
      {l.ticket_number && <span className="text-emerald-300">{l.ticket_number}</span>}
    </div>
  );
};

export default function SuperAIActivity() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState({ start: "", end: "" });
  const [societies, setSocieties] = useState([]);
  const [society, setSociety] = useState("all");

  useEffect(() => {
    api.get("/super/societies").then((r) => setSocieties(r.data || [])).catch(() => setSocieties([]));
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = { society_id: society };
    if (range.start) params.start = range.start;
    if (range.end) params.end = range.end;
    api.get("/super/ai-activity", { params }).then((r) => setData(r.data)).finally(() => setLoading(false));
  }, [range, society]);

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="AI Activity" subtitle="Detection feed across every society">
        <div className="flex flex-wrap items-center gap-2">
          <Select value={society} onValueChange={setSociety}>
            <SelectTrigger className="w-56" data-testid="ai-society-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all" data-testid="ai-society-option-all">All societies</SelectItem>
              {societies.map((s) => <SelectItem key={s.id} value={s.id} data-testid={`ai-society-option-${s.id}`}>{s.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <DateRangeFilter onChange={setRange} testidPrefix="ai-range" />
        </div>
      </PageHeader>

      {loading || !data ? (
        <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-zinc-400" /></div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            <StatCard testid="ai-stat-total" label="Processed" value={data.stats.total} icon={Activity} />
            <StatCard testid="ai-stat-detected" label="Tickets Created" value={data.stats.detected} icon={Bot} accent="text-emerald-600" />
            <StatCard testid="ai-stat-review" label="Needs Review" value={data.stats.review} icon={ClipboardCheck} accent="text-amber-600" />
            <StatCard testid="ai-stat-dupe" label="Duplicates" value={data.stats.duplicate} icon={Copy} accent="text-sky-600" />
            <StatCard testid="ai-stat-ignored" label="Ignored" value={data.stats.ignored} icon={EyeOff} accent="text-zinc-400" />
          </div>
          <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900 p-5" data-testid="ai-log-panel">
            <p className="mb-4 font-mono text-xs uppercase tracking-[0.2em] text-amber-400">// processing logs</p>
            <div className="max-h-[560px] space-y-2 overflow-y-auto font-mono text-xs">
              {data.logs.length === 0
                ? <p className="text-zinc-400" data-testid="ai-log-empty">No activity in this period.</p>
                : data.logs.map((l) => <LogRow key={l.id} l={l} />)}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
