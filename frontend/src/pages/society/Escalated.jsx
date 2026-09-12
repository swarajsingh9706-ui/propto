import { useNavigate } from "react-router-dom";
import { useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Panel, SLABar } from "@/components/DashKit";
import { Loader2, AlertTriangle } from "lucide-react";

function slaHours(t) {
  if (!t.sla_due || !t.created_at) return null;
  const h = (new Date(t.sla_due).getTime() - new Date(t.created_at).getTime()) / 3600000;
  return h > 0 ? Math.round(h) : null;
}

export default function Escalated() {
  const navigate = useNavigate();
  const { data, loading } = useFetch("/society/tickets/escalated");
  const rows = data || [];

  return (
    <div className="p-4 sm:p-6 lg:p-8" data-testid="escalated-page">
      <PageHeader title="Escalated Tickets" subtitle="Needs Manual Action" />
      <Panel
        danger
        testid="escalated-panel"
        title={
          <span className="flex items-center gap-2 text-red-600">
            <AlertTriangle className="h-4 w-4" />
            <span>
              <span className="block text-[14px] font-extrabold">Escalated Tickets</span>
              <span className="block text-[11px] font-normal text-slate-500">Require manual assignment — AI routing exhausted or SLA breached</span>
            </span>
          </span>
        }
        action={<span className="rounded-full border border-red-200 bg-red-50 px-2.5 py-0.5 text-[11px] font-bold text-red-600" data-testid="escalated-count">{rows.length} pending</span>}
      >
        <div className="grid grid-cols-[90px_1.2fr_0.8fr_1fr_1.4fr_1.3fr_120px] gap-2 border-b border-border bg-slate-50 px-[18px] py-2">
          {["TICKET ID", "ISSUE", "UNIT", "RESIDENT", "REASON", "SLA", "ACTION"].map((h) => <div key={h} className="text-[9px] font-extrabold uppercase tracking-wide text-slate-400">{h}</div>)}
        </div>
        {loading ? <div className="p-6"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div> :
          rows.length === 0 ? <div className="p-10 text-center text-sm text-slate-400"><AlertTriangle className="mx-auto mb-2 h-8 w-8 text-slate-300" />No escalated tickets. Everything is on track.</div> :
            rows.map((t, i) => (
              <div key={t.id} data-testid={`escalated-row-${t.id}`} className="grid grid-cols-[90px_1.2fr_0.8fr_1fr_1.4fr_1.3fr_120px] items-center gap-2 border-b border-border px-[18px] py-3" style={{ background: i % 2 ? "#f8fafc" : "#fff", borderLeft: "3px solid #dc2626" }}>
                <div className="text-[12px] font-extrabold text-red-600">{t.ticket_number || t.id?.slice(-6)}</div>
                <div className="text-[13px] font-semibold text-slate-900">{t.title || t.category || "Issue"}</div>
                <div className="text-[12px] text-slate-500">{t.flat || t.unit || t.tower || "—"}</div>
                <div className="text-[12px] text-slate-500">{t.reporter_name || t.resident_name || "Resident"}</div>
                <div className="text-[11px] font-semibold text-amber-600">{t.escalation_reason || (t.status === "Escalated" ? "AI routing exhausted" : "SLA breached")}</div>
                <SLABar createdAt={t.created_at} slaHours={slaHours(t)} />
                <button data-testid={`assign-${t.id}`} onClick={() => navigate("/tickets")} className="whitespace-nowrap rounded-[7px] bg-brand px-3 py-1.5 text-[11px] font-bold text-white hover:opacity-90">Assign Now →</button>
              </div>
            ))}
      </Panel>
    </div>
  );
}
