import { useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Panel } from "@/components/DashKit";
import { Loader2, MessageSquare, Bot, ListChecks, Wrench, UserCog, ArrowRight } from "lucide-react";

const STEPS = [
  { icon: MessageSquare, color: "#2563eb", bg: "#dbeafe", title: "1. WhatsApp message", desc: "Resident posts in the connected society group." },
  { icon: ListChecks, color: "#7c3aed", bg: "#ede9fe", title: "2. Pre-filter", desc: "Greetings, ads and spam are dropped before any AI call." },
  { icon: Bot, color: "#059669", bg: "#d1fae5", title: "3. Gemini AI", desc: "Decides if it is a genuine complaint and extracts flat, priority & description." },
  { icon: ListChecks, color: "#d97706", bg: "#fef3c7", title: "4. 10,000-issue taxonomy", desc: "Matched issue sets category, severity, SLA and who handles it." },
  { icon: UserCog, color: "#0891b2", bg: "#cffafe", title: "5a. Society Manager", desc: "Admin / committee-owned issues stay in-house for the manager." },
  { icon: Wrench, color: "#dc2626", bg: "#fee2e2", title: "5b. Vendor routing", desc: "Vendor-owned issues auto-assign to an available vendor in that category." },
];

export default function AssignmentLogic() {
  const { data, loading } = useFetch("/society/assignment-config");
  const cfg = data || { sla: [], coverage: [], vendor_count: 0 };

  return (
    <div className="p-8" data-testid="assignment-logic-page">
      <PageHeader title="Ticket Assignment Logic" subtitle="Routing Rules" />

      <Panel title="How a message becomes an assigned ticket" testid="flow-panel">
        <div className="grid grid-cols-1 gap-3 p-[18px] md:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((s) => (
            <div key={s.title} data-testid={`flow-step-${s.title}`} className="rounded-xl border border-border bg-white p-4">
              <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg" style={{ background: s.bg }}>
                <s.icon className="h-[18px] w-[18px]" style={{ color: s.color }} />
              </div>
              <div className="text-[13px] font-extrabold text-slate-900">{s.title}</div>
              <div className="mt-1 text-[12px] leading-relaxed text-slate-500">{s.desc}</div>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 border-t border-border px-[18px] py-3 text-[12px] font-semibold text-slate-500">
          Complaint <ArrowRight className="h-3.5 w-3.5" /> Gemini <ArrowRight className="h-3.5 w-3.5" /> Taxonomy <ArrowRight className="h-3.5 w-3.5" /> Manager or Vendor <ArrowRight className="h-3.5 w-3.5" /> Ticket created & confirmation sent
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="SLA by severity" testid="sla-panel">
          <div className="grid grid-cols-[1fr_1fr] gap-2.5 border-b border-border bg-slate-50 px-[18px] py-2">
            {["SEVERITY", "SLA TARGET"].map((h) => <div key={h} className="text-[10px] font-extrabold uppercase tracking-wide text-slate-400">{h}</div>)}
          </div>
          {loading ? <div className="p-6"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div> :
            cfg.sla.map((s, i) => (
              <div key={s.severity} className="grid grid-cols-[1fr_1fr] items-center gap-2.5 border-b border-border px-[18px] py-3" style={{ background: i % 2 ? "#f8fafc" : "#fff" }}>
                <span className="inline-flex items-center gap-1.5 text-[13px] font-bold" style={{ color: s.color }}>
                  <span className="inline-block h-[7px] w-[7px] rounded-full" style={{ background: s.color }} />{s.severity}
                </span>
                <span className="text-[13px] text-slate-700">Within {s.hours} {s.hours === 1 ? "hour" : "hours"}</span>
              </div>
            ))}
        </Panel>

        <Panel title={`Vendor coverage (${cfg.vendor_count} active)`} testid="coverage-panel">
          <div className="grid grid-cols-[1.4fr_0.6fr] gap-2.5 border-b border-border bg-slate-50 px-[18px] py-2">
            {["CATEGORY", "VENDORS"].map((h) => <div key={h} className="text-[10px] font-extrabold uppercase tracking-wide text-slate-400">{h}</div>)}
          </div>
          {loading ? <div className="p-6"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div> :
            cfg.coverage.length === 0 ? <div className="p-8 text-center text-[13px] text-slate-400">No active vendors — add vendors so tickets can auto-assign.</div> :
              cfg.coverage.map((c, i) => (
                <div key={c.category} className="grid grid-cols-[1.4fr_0.6fr] items-center gap-2.5 border-b border-border px-[18px] py-3" style={{ background: i % 2 ? "#f8fafc" : "#fff" }}>
                  <div className="text-[13px] font-semibold text-slate-900">{c.category}</div>
                  <div className="text-[13px]" style={{ color: c.vendors ? "#16a34a" : "#dc2626", fontWeight: 700 }}>{c.vendors} available</div>
                </div>
              ))}
        </Panel>
      </div>
    </div>
  );
}
