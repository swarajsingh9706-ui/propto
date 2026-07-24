import { PageHeader } from "@/components/Layout";
import { StatCard } from "@/components/StatCard";
import { useFetch } from "@/lib/useScope";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import { Loader2, Ticket, Wrench, Users, Building2, CheckCircle2, Clock, AlertTriangle, Bot } from "lucide-react";
import { StatusBadge, PriorityBadge } from "@/components/Badges";

const COLORS = ["#2563EB", "#D97706", "#059669", "#DC2626", "#0284C7", "#7c3aed", "#0891b2"];

export default function Dashboard() {
  const { data, loading } = useFetch("/society/dashboard");
  if (loading || !data) return <Center />;
  const { stats, recent, by_category, status_dist } = data;

  return (
    <div className="p-8">
      <PageHeader title="Dashboard" subtitle="Society Overview" />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        <StatCard testid="stat-total" label="Total Complaints" value={stats.total} icon={Ticket} />
        <StatCard testid="stat-open" label="Open" value={stats.open} icon={Clock} accent="text-blue-600" />
        <StatCard testid="stat-pending" label="Pending" value={stats.pending} icon={Clock} accent="text-amber-600" />
        <StatCard testid="stat-resolved" label="Resolved" value={stats.resolved} icon={CheckCircle2} accent="text-emerald-600" />
        <StatCard testid="stat-escalated" label="Escalated" value={stats.escalated} icon={AlertTriangle} accent="text-red-600" />
        <StatCard testid="stat-ai" label="AI Generated" value={stats.ai_generated} icon={Bot} accent="text-sky-600" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-border bg-card p-6 lg:col-span-2">
          <p className="overline mb-4">Complaints by Category</p>
          {by_category.length === 0 ? <NoData /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={by_category} margin={{ left: -20 }}>
                <XAxis dataKey="category" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ border: "1px solid #e4e4e7", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" fill="#18181B" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="rounded-lg border border-border bg-card p-6">
          <p className="overline mb-4">Status Distribution</p>
          {stats.total === 0 ? <NoData /> : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={status_dist} dataKey="count" nameKey="status" innerRadius={55} outerRadius={90} paddingAngle={2}>
                  {status_dist.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ border: "1px solid #e4e4e7", borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="mt-6 rounded-lg border border-border bg-card">
        <p className="overline border-b border-border px-6 py-4">Recent Tickets</p>
        {recent.length === 0 ? <div className="p-6"><NoData /></div> : (
          <table className="w-full text-sm">
            <tbody>
              {recent.map((t) => (
                <tr key={t.id} className="border-b border-border last:border-0 hover:bg-secondary/50">
                  <td className="px-6 py-3 font-mono text-xs text-zinc-500">{t.ticket_number}</td>
                  <td className="px-6 py-3 font-medium">{t.category}</td>
                  <td className="px-6 py-3 text-zinc-500">Flat {t.flat || "—"}</td>
                  <td className="px-6 py-3"><PriorityBadge priority={t.priority} /></td>
                  <td className="px-6 py-3"><StatusBadge status={t.status} /></td>
                  <td className="px-6 py-3 text-right text-zinc-400">{t.vendor_name || "Unassigned"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const Center = () => <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-zinc-400" /></div>;
const NoData = () => <div className="flex h-40 items-center justify-center text-sm text-zinc-400">No data yet</div>;
