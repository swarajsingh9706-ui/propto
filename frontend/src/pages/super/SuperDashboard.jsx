import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useFetch } from "@/lib/useScope";
import { TopHeader, DashStat, Panel } from "@/components/DashKit";
import { StatusBadge } from "@/components/Badges";
import {
  Loader2, Building2, CircleCheck, Ticket, Clock, AlertTriangle, Timer,
  CheckCircle2, Wrench, ArrowRight,
} from "lucide-react";

const STATS = [
  { key: "societies", label: "Societies", sub: "On the platform", color: "#2563eb", iconBg: "#dbeafe", icon: Building2 },
  { key: "active_societies", label: "Active", sub: "Currently live", color: "#22c55e", iconBg: "#dcfce7", icon: CircleCheck },
  { key: "total_tickets", label: "Total Tickets", sub: "Across all societies", color: "#4f46e5", iconBg: "#e0e7ff", icon: Ticket },
  { key: "open", label: "Open", sub: "Awaiting action", color: "#f59e0b", iconBg: "#fef3c7", icon: Clock },
  { key: "escalated", label: "Escalated", sub: "Needs attention", color: "#ef4444", iconBg: "#fee2e2", icon: AlertTriangle },
  { key: "resolved", label: "Resolved", sub: "Closed tickets", color: "#06b6d4", iconBg: "#cffafe", icon: CheckCircle2 },
];

export default function SuperDashboard() {
  const { user, scopeInto } = useAuth();
  const navigate = useNavigate();
  const { data, loading } = useFetch("/super/dashboard");
  if (loading || !data) return <Center />;
  const { stats, societies, categories } = data;
  const firstName = (user?.name || "Admin").split(" ")[0];
  const manage = (id) => { scopeInto(id); navigate("/dashboard"); };

  return (
    <div className="flex min-h-screen flex-col">
      <TopHeader greeting={`Welcome back, ${firstName}!`} subtitle="Platform overview across all your societies" />
      <div className="flex gap-5 px-6 py-5">
        <div className="min-w-0 flex-1">
          <div className="mb-4 grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
            {STATS.map((s) => (
              <DashStat key={s.key} testid={`super-stat-${s.key}`} value={stats[s.key] ?? 0} label={s.label}
                sub={s.sub} color={s.color} iconBg={s.iconBg} icon={s.icon} />
            ))}
          </div>

          <Panel testid="panel-societies" title="Societies Overview"
            action={<button data-testid="societies-manage-all" onClick={() => navigate("/super/societies")} className="text-[12px] font-bold text-brand">Manage all</button>}>
            {societies.length === 0 ? (
              <EmptyRow text="No societies yet. Add your first society to get started." />
            ) : (
              <>
                <RowHead cols="1.4fr 0.8fr 0.7fr 0.7fr 0.8fr 0.9fr 110px"
                  items={["SOCIETY", "STATUS", "TICKETS", "OPEN", "ESCALATED", "RESOLVED", "ACTION"]} />
                {societies.map((s, i) => (
                  <div key={s.id} className="grid items-center gap-2 border-b border-border px-[18px] py-3 last:border-0"
                    style={{ gridTemplateColumns: "1.4fr 0.8fr 0.7fr 0.7fr 0.8fr 0.9fr 110px", background: i % 2 ? "#f8fafc" : "#fff" }}>
                    <div>
                      <div className="truncate text-[13px] font-bold text-slate-900">{s.name}</div>
                      <div className="text-[11px] text-slate-400">{s.code} · {s.city || "—"}</div>
                    </div>
                    <StatusBadge status={s.active ? "Resolved" : "Escalated"} />
                    <div className="text-[13px] font-semibold text-slate-700">{s.total}</div>
                    <div className="text-[13px] text-amber-600">{s.open}</div>
                    <div className="text-[13px] font-bold text-red-600">{s.escalated}</div>
                    <div className="text-[13px] text-green-600">{s.resolved}</div>
                    <button data-testid={`super-manage-${s.code}`} onClick={() => manage(s.id)}
                      className="inline-flex items-center gap-1 whitespace-nowrap rounded-[7px] bg-brand px-3 py-1.5 text-[11px] font-bold text-white hover:opacity-90">
                      Manage <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </>
            )}
          </Panel>
        </div>

        <div className="hidden w-[300px] flex-shrink-0 flex-col gap-3.5 xl:flex">
          <div className="grid grid-cols-1 gap-3.5">
            <DashStat testid="super-stat-overdue" value={stats.overdue ?? 0} label="Overdue Tickets" sub="Past SLA target" color="#ef4444" iconBg="#fee2e2" icon={Timer} />
            <DashStat testid="super-stat-vendors" value={stats.vendors ?? 0} label="Vendors" sub="Across platform" color="#7c3aed" iconBg="#f5f3ff" icon={Wrench} />
          </div>

          <Panel testid="panel-categories" title="Top Categories">
            {categories.length === 0 ? (
              <div className="px-4 py-6 text-center text-[12px] text-slate-400">No data yet</div>
            ) : categories.map((c, i) => {
              const max = categories[0].count || 1;
              const pct = Math.round((c.count / max) * 100);
              const bar = ["#2563eb", "#4f46e5", "#06b6d4", "#22c55e", "#f59e0b", "#8b5cf6"][i % 6];
              return (
                <div key={c.category} className="border-b border-border px-4 py-3 last:border-0">
                  <div className="mb-1.5 flex justify-between text-[12px]">
                    <span className="truncate font-semibold text-slate-700">{c.category}</span>
                    <span className="font-bold text-slate-500">{c.count}</span>
                  </div>
                  <div className="h-[5px] rounded bg-slate-100">
                    <div className="h-[5px] rounded" style={{ width: `${pct}%`, background: bar }} />
                  </div>
                </div>
              );
            })}
          </Panel>
        </div>
      </div>
    </div>
  );
}

const RowHead = ({ cols, items }) => (
  <div className="grid gap-2 border-b border-border bg-slate-50 px-[18px] py-2" style={{ gridTemplateColumns: cols }}>
    {items.map((h) => (
      <div key={h} className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">{h}</div>
    ))}
  </div>
);
const EmptyRow = ({ text }) => <div className="px-[18px] py-8 text-center text-[13px] text-slate-400">{text}</div>;
const Center = () => <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
