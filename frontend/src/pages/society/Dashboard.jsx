import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useScope, useFetch } from "@/lib/useScope";
import api from "@/lib/api";
import { TopHeader, DashStat, Panel, PriorityDot, SLABar } from "@/components/DashKit";
import { StatusBadge } from "@/components/Badges";
import {
  Loader2, Ticket, AlertTriangle, Clock, Timer, UserCheck, CheckCircle2,
  Package, Wrench, ClipboardList, HardHat, BarChart3,
} from "lucide-react";

const STATS = [
  { key: "total", label: "Total Tickets", sub: "All tickets", color: "#2563eb", iconBg: "#dbeafe", icon: Ticket },
  { key: "escalated", label: "Escalated", sub: "Needs your action", color: "#ef4444", iconBg: "#fee2e2", icon: AlertTriangle },
  { key: "open", label: "Open", sub: "Awaiting assignment", color: "#f59e0b", iconBg: "#fef3c7", icon: Clock },
  { key: "overdue", label: "Overdue Tickets", sub: "Past SLA target", color: "#ef4444", iconBg: "#fee2e2", icon: Timer },
  { key: "assigned", label: "Assigned", sub: "Confirmed vendors", color: "#22c55e", iconBg: "#dcfce7", icon: UserCheck },
  { key: "resolved_today", label: "Resolved Today", sub: "Marked resolved", color: "#06b6d4", iconBg: "#cffafe", icon: CheckCircle2 },
];

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const cfg = useScope();
  const { data, loading } = useFetch("/society/dashboard");
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    api.get("/society/suggestions", cfg).then((r) => setSuggestions(r.data.suggestions || [])).catch(() => {});
    // eslint-disable-next-line
  }, []);

  if (loading || !data) return <Center />;
  const { stats, recent, escalated, maintenance = [] } = data;
  const firstName = (user?.name || "there").split(" ")[0];

  return (
    <div className="flex min-h-screen flex-col">
      <TopHeader greeting={`Good day, ${firstName}!`} subtitle="Here's what's happening at your society" />

      <div className="flex flex-col gap-5 px-4 py-5 sm:px-6 xl:flex-row">
        {/* MAIN COLUMN */}
        <div className="min-w-0 flex-1">
          <div className="mb-4 grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
            {STATS.map((s) => (
              <DashStat key={s.key} testid={`stat-${s.key}`} value={stats[s.key] ?? 0} label={s.label}
                sub={s.sub} color={s.color} iconBg={s.iconBg} icon={s.icon} />
            ))}
          </div>

          <div className="mb-4 flex flex-col gap-3 sm:flex-row">
            <SummaryCard icon={Package} iconBg="#dcfce7" label="Assets" value={stats.assets ?? 0} onClick={() => navigate("/assets")} testid="summary-assets" />
            <SummaryCard icon={ClipboardList} iconBg="#dbeafe" label="Vendors" value={stats.vendors} onClick={() => navigate("/vendors")} testid="summary-vendors" />
          </div>

          <Panel testid="panel-escalated" danger
            title="Escalated Tickets"
            icon={<AlertTriangle className="h-4 w-4 text-red-600" />}
            action={<button data-testid="escalated-viewall" onClick={() => navigate("/escalated")} className="text-[12px] font-bold text-brand">View all</button>}>
            {escalated.length === 0 ? (
              <EmptyRow text="No escalated tickets — everything is under control." />
            ) : (
              <div className="overflow-x-auto">
                <div className="min-w-[640px]">
                <RowHead cols="90px 1.4fr 0.8fr 1fr 1.4fr 120px" items={["TICKET ID", "ISSUE", "UNIT", "RESIDENT", "SLA", "ACTION"]} />
                {escalated.map((t, i) => (
                  <div key={t.id} className="grid items-center gap-2 border-b border-border px-[18px] py-3 last:border-0"
                    style={{ gridTemplateColumns: "90px 1.4fr 0.8fr 1fr 1.4fr 120px", borderLeft: "3px solid #dc2626", background: i % 2 ? "#f8fafc" : "#fff" }}>
                    <div className="text-[12px] font-extrabold text-red-600">{t.ticket_number?.slice(-6)}</div>
                    <div className="truncate text-[13px] font-semibold text-slate-900">{t.category}</div>
                    <div className="text-[12px] text-slate-500">{t.flat || "—"}</div>
                    <div className="truncate text-[12px] text-slate-500">{t.resident_name || "—"}</div>
                    <SLABar createdAt={t.created_at} slaHours={t.sla_hours} />
                    <button data-testid={`assign-now-${t.id}`} onClick={() => navigate("/escalated")}
                      className="whitespace-nowrap rounded-[7px] bg-brand px-3 py-1.5 text-[11px] font-bold text-white hover:opacity-90">
                      Assign Now →
                    </button>
                  </div>
                ))}
                </div>
              </div>
            )}
          </Panel>

          <Panel testid="panel-recent" title="Recent Tickets"
            action={<button data-testid="recent-viewall" onClick={() => navigate("/tickets")} className="text-[12px] font-bold text-brand">View all</button>}>
            {recent.length === 0 ? (
              <EmptyRow text="No tickets yet." />
            ) : (
              <div className="overflow-x-auto">
                <div className="min-w-[640px]">
                <RowHead cols="90px 1fr 0.8fr 0.9fr 0.9fr 1fr" items={["ID", "ISSUE", "UNIT", "STATUS", "PRIORITY", "ASSIGNED TO"]} />
                {recent.map((t, i) => (
                  <div key={t.id} className="grid items-center gap-2.5 border-b border-border px-[18px] py-3 last:border-0"
                    style={{ gridTemplateColumns: "90px 1fr 0.8fr 0.9fr 0.9fr 1fr", background: i % 2 ? "#f8fafc" : "#fff" }}>
                    <div className="text-[12px] font-extrabold text-brand">{t.ticket_number?.slice(-6)}</div>
                    <div className="truncate text-[13px] text-slate-700">{t.category}</div>
                    <div className="text-[12px] text-slate-500">{t.flat || "—"}</div>
                    <StatusBadge status={t.status} />
                    <PriorityDot priority={t.priority} />
                    <div className="truncate text-[12px] text-slate-500">{t.vendor_name || "Unassigned"}</div>
                  </div>
                ))}
                </div>
              </div>
            )}
          </Panel>

          <Panel testid="panel-maintenance" title="Upcoming Maintenance"
            action={<button data-testid="maintenance-viewall" onClick={() => navigate("/assets")} className="text-[12px] font-bold text-brand">View all</button>}>
            {maintenance.length === 0 ? (
              <EmptyRow text="No scheduled maintenance yet — add service dates on the Assets page." />
            ) : (
              <div className="overflow-x-auto">
                <div className="min-w-[560px]">
                <RowHead cols="1.5fr 1fr 1fr 1.1fr" items={["ASSET", "TYPE", "DUE DATE", "STATUS"]} />
                {maintenance.map((a, i) => (
                  <div key={a.id} className="grid items-center gap-2.5 border-b border-border px-[18px] py-3 last:border-0"
                    style={{ gridTemplateColumns: "1.5fr 1fr 1fr 1.1fr", background: i % 2 ? "#f8fafc" : "#fff" }}>
                    <div className="text-[13px] font-bold text-slate-900">{a.name}</div>
                    <div className="text-[12px] text-slate-500">{a.type || "—"}</div>
                    <div className="text-[12px] text-slate-700">{a.next_service || "—"}</div>
                    <div><MaintBadge s={a.status} /></div>
                  </div>
                ))}
                </div>
              </div>
            )}
          </Panel>
        </div>

        {/* RIGHT RAIL */}
        <div className="flex w-full flex-shrink-0 flex-col gap-3.5 xl:w-[300px]">
          <Panel testid="panel-alerts" title="Alerts"
            action={<button onClick={() => navigate("/notifications")} className="text-[12px] font-bold text-brand">View all</button>}>
            {escalated.length === 0 && maintenance.filter((a) => ["Overdue", "Due Soon"].includes(a.status)).length === 0 ? (
              <div className="px-4 py-6 text-center text-[12px] text-slate-400">No active alerts</div>
            ) : (
              <>
                {escalated.slice(0, 4).map((t) => (
                  <div key={t.id} className="flex items-start gap-2.5 border-b border-border px-4 py-2.5 last:border-0">
                    <AlertTriangle className="mt-0.5 h-[15px] w-[15px] flex-shrink-0 text-red-600" />
                    <div className="flex-1">
                      <div className="text-[12px] font-bold text-red-600">Ticket {t.ticket_number?.slice(-6)} needs action</div>
                      <div className="mt-0.5 text-[11px] text-slate-500">{t.category} · {t.flat || "—"}</div>
                    </div>
                  </div>
                ))}
                {maintenance.filter((a) => ["Overdue", "Due Soon"].includes(a.status)).slice(0, 3).map((a) => (
                  <div key={a.id} className="flex items-start gap-2.5 border-b border-border px-4 py-2.5 last:border-0">
                    <Package className={`mt-0.5 h-[15px] w-[15px] flex-shrink-0 ${a.status === "Overdue" ? "text-red-600" : "text-amber-600"}`} />
                    <div className="flex-1">
                      <div className={`text-[12px] font-bold ${a.status === "Overdue" ? "text-red-600" : "text-amber-600"}`}>Asset service {a.status === "Overdue" ? "overdue" : "due soon"}</div>
                      <div className="mt-0.5 text-[11px] text-slate-500">{a.name} · {a.next_service}</div>
                    </div>
                  </div>
                ))}
              </>
            )}
          </Panel>

          <Panel testid="panel-suggestions" title="Resident Suggestions"
            icon={<span className="text-[14px]">📋</span>}
            action={<button onClick={() => navigate("/suggestions")} className="text-[12px] font-bold text-brand">View all</button>}>
            {suggestions.length === 0 ? (
              <div className="px-4 py-6 text-center text-[12px] text-slate-400">No suggestions yet</div>
            ) : suggestions.slice(0, 3).map((s, i) => {
              const yes = s.yes_votes || 0, no = s.no_votes || 0, tot = yes + no;
              const pct = tot ? Math.round((yes / tot) * 100) : 0;
              const bar = ["#22c55e", "#2563eb", "#8b5cf6"][i % 3];
              return (
                <div key={s.id} className="border-b border-border px-4 py-3 last:border-0">
                  <div className="mb-1 text-[13px] font-bold text-slate-900">{s.title}</div>
                  <div className="mb-2 text-[11px] text-slate-400">{s.author_name || "Resident"} · {s.flat || "—"}</div>
                  <div className="mb-1.5 h-[5px] rounded bg-slate-100">
                    <div className="h-[5px] rounded" style={{ width: `${pct}%`, background: bar }} />
                  </div>
                  <div className="flex justify-between text-[11px] font-bold">
                    <span className="text-green-600">✓ Yes {yes}</span>
                    <span className="text-red-600">✗ No {no}</span>
                  </div>
                </div>
              );
            })}
          </Panel>

          <div className="rounded-xl border border-border bg-white p-4 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
            <div className="mb-3 text-[13px] font-extrabold text-slate-900">Quick Actions</div>
            <div className="grid grid-cols-2 gap-2.5">
              <QuickAction icon={ClipboardList} label="Tickets" color="#2563eb" bg="#eff6ff" border="#bfdbfe" onClick={() => navigate("/tickets")} testid="qa-tickets" />
              <QuickAction icon={Wrench} label="Add Vendor" color="#16a34a" bg="#dcfce7" border="#86efac" onClick={() => navigate("/vendors")} testid="qa-vendor" />
              <QuickAction icon={HardHat} label="Residents" color="#7c3aed" bg="#f5f3ff" border="#ddd6fe" onClick={() => navigate("/residents")} testid="qa-residents" />
              <QuickAction icon={BarChart3} label="View Reports" color="#d97706" bg="#fef3c7" border="#fde68a" onClick={() => navigate("/reports")} testid="qa-reports" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const SummaryCard = ({ icon: Icon, iconBg, label, value, onClick, testid }) => (
  <div data-testid={testid} className="flex flex-1 items-center justify-between rounded-xl border border-border bg-white px-[18px] py-3.5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
    <div className="flex items-center gap-3">
      <div className="flex h-[38px] w-[38px] items-center justify-center rounded-[10px]" style={{ background: iconBg }}>
        <Icon className="h-[18px] w-[18px] text-slate-700" />
      </div>
      <div>
        <div className="text-[11px] font-semibold text-slate-400">{label}</div>
        <div className="text-[26px] font-black leading-tight text-slate-900">{value}</div>
      </div>
    </div>
    <button onClick={onClick} className="text-[13px] font-bold text-brand">View all ›</button>
  </div>
);

const QuickAction = ({ icon: Icon, label, color, bg, border, onClick, testid }) => (
  <button data-testid={testid} onClick={onClick}
    className="rounded-[10px] p-3.5 text-left transition-transform hover:-translate-y-0.5"
    style={{ background: bg, border: `1px solid ${border}` }}>
    <Icon className="mb-1.5 h-[18px] w-[18px]" style={{ color }} />
    <div className="text-[12px] font-bold" style={{ color }}>{label}</div>
  </button>
);

const RowHead = ({ cols, items }) => (
  <div className="grid gap-2 border-b border-border bg-slate-50 px-[18px] py-2" style={{ gridTemplateColumns: cols }}>
    {items.map((h) => (
      <div key={h} className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">{h}</div>
    ))}
  </div>
);
const EmptyRow = ({ text }) => <div className="px-[18px] py-8 text-center text-[13px] text-slate-400">{text}</div>;
const MAINT_BADGE = {
  "Due Soon": ["#fffbeb", "#d97706"], Overdue: ["#fef2f2", "#dc2626"],
  Scheduled: ["#dcfce7", "#16a34a"], Unscheduled: ["#f1f5f9", "#64748b"],
};
const MaintBadge = ({ s }) => {
  const [bg, fg] = MAINT_BADGE[s] || MAINT_BADGE.Scheduled;
  return <span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: bg, color: fg }}>{s === "Unscheduled" ? "Not Scheduled" : s}</span>;
};
const Center = () => <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
