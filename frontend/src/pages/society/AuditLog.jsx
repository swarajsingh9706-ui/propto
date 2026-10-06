import { useEffect, useState } from "react";
import api from "@/lib/api";
import { useScope } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { DateRangeFilter } from "@/components/DateRangeFilter";
import {
  Loader2, Ticket, Wrench, Users, MessageSquare, Vote, Building2, ScrollText,
} from "lucide-react";

const CATS = [
  { key: "all", label: "All Activity" },
  { key: "ticket", label: "Tickets" },
  { key: "vendor", label: "Vendors" },
  { key: "resident", label: "Residents" },
  { key: "suggestion", label: "Suggestions" },
  { key: "whatsapp", label: "WhatsApp" },
];
const ICON = { ticket: Ticket, vendor: Wrench, resident: Users, suggestion: Vote, whatsapp: MessageSquare, society: Building2, general: ScrollText };
const COLOR = { ticket: "#2563eb", vendor: "#7c3aed", resident: "#16a34a", suggestion: "#d97706", whatsapp: "#06b6d4", society: "#4f46e5", general: "#64748b" };
const BG = { ticket: "#dbeafe", vendor: "#f5f3ff", resident: "#dcfce7", suggestion: "#fef3c7", whatsapp: "#cffafe", society: "#e0e7ff", general: "#f1f5f9" };

function timeAgo(iso) {
  const d = new Date(iso);
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`;
  return d.toLocaleDateString();
}

function fmtDT(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return "—";
  return d.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function AuditLog() {
  const cfg = useScope();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cat, setCat] = useState("all");
  const [range, setRange] = useState({ start: "", end: "" });

  useEffect(() => {
    setLoading(true);
    const params = { ...cfg.params };
    if (cat !== "all") params.category = cat;
    if (range.start) params.start = range.start;
    if (range.end) params.end = range.end;
    api.get("/society/audit", { params })
      .then((r) => setRows(r.data || []))
      .finally(() => setLoading(false));
    // eslint-disable-next-line
  }, [cat, range, cfg.params?.society_id]);

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Audit Log" subtitle="Activity Trail" description="Track record of every action">
        <DateRangeFilter onChange={setRange} testidPrefix="audit-range" />
      </PageHeader>

      <div className="mb-5 flex flex-wrap gap-2">
        {CATS.map((c) => (
          <button key={c.key} data-testid={`audit-filter-${c.key}`} onClick={() => setCat(c.key)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors ${
              cat === c.key ? "border-brand bg-brand text-white" : "border-border bg-white text-zinc-600 hover:bg-secondary"}`}>
            {c.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-white p-12 text-center text-sm text-zinc-400">
          <ScrollText className="mx-auto mb-3 h-8 w-8 text-zinc-300" />
          No activity recorded for the selected filters.
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          {rows.map((r) => {
            const Icon = ICON[r.category] || ScrollText;
            const color = COLOR[r.category] || COLOR.general;
            return (
              <div key={r.id} data-testid={`audit-row-${r.id}`}
                className="flex items-start gap-3 border-b border-border px-5 py-3.5 last:border-0 hover:bg-secondary/40">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg" style={{ background: BG[r.category] || BG.general }}>
                  <Icon className="h-[18px] w-[18px]" style={{ color }} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-900">{r.summary}</p>
                  <p className="mt-0.5 text-xs text-zinc-400">
                    by <span className="font-medium text-zinc-500">{r.actor}</span>
                    {r.ticket_number && <> · <span className="font-mono text-[11px] text-brand">{r.ticket_number}</span></>}
                  </p>
                </div>
                <span className="whitespace-nowrap text-right">
                  <span className="block text-xs font-medium text-zinc-600" data-testid={`audit-datetime-${r.id}`}>{fmtDT(r.created_at)}</span>
                  <span className="block text-[11px] text-zinc-400">{timeAgo(r.created_at)}</span>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
