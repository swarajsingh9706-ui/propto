import { PageHeader } from "@/components/Layout";
import { StatCard } from "@/components/StatCard";
import { useFetch } from "@/lib/useScope";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Loader2, Building2, Ticket, Wrench, Users } from "lucide-react";

export default function SuperReports() {
  const { data, loading } = useFetch("/super/reports");
  if (loading || !data) return <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-zinc-400" /></div>;
  const { societies, categories, vendor_performance, totals } = data;

  return (
    <div className="p-8">
      <PageHeader title="Platform Analytics" subtitle="Super Admin" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard testid="sr-societies" label="Societies" value={totals.societies} icon={Building2} />
        <StatCard testid="sr-tickets" label="Total Tickets" value={totals.tickets} icon={Ticket} />
        <StatCard testid="sr-vendors" label="Vendors" value={totals.vendors} icon={Wrench} />
        <StatCard testid="sr-residents" label="Residents" value={totals.residents} icon={Users} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-6">
          <p className="overline mb-4">Complaint Categories (all societies)</p>
          {categories.length === 0 ? <NoData /> : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={categories} layout="vertical" margin={{ left: 30 }}>
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="category" width={90} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ border: "1px solid #e4e4e7", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" fill="#18181B" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <div className="rounded-lg border border-border bg-card p-6">
          <p className="overline mb-4">Vendor Performance</p>
          {vendor_performance.length === 0 ? <NoData /> : (
            <div className="space-y-3">
              {vendor_performance.map((v, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="w-32 truncate text-sm">{v.vendor}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${v.rate}%` }} /></div>
                  <span className="w-24 text-right text-xs text-zinc-500">{v.resolved}/{v.assigned} · {v.rate}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-lg border border-border bg-card">
        <p className="overline border-b border-border px-6 py-4">Society-wise Report</p>
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-secondary/50 text-left text-[11px] uppercase tracking-wider text-zinc-500">
            <tr><th className="px-6 py-3 font-medium">Society</th><th className="px-6 py-3 font-medium">Code</th><th className="px-6 py-3 font-medium">Total</th><th className="px-6 py-3 font-medium">Open</th><th className="px-6 py-3 font-medium">Resolved</th><th className="px-6 py-3 font-medium">Status</th></tr>
          </thead>
          <tbody>
            {societies.map((s, i) => (
              <tr key={i} className="border-b border-border last:border-0 hover:bg-secondary/50">
                <td className="px-6 py-3 font-medium">{s.society}</td>
                <td className="px-6 py-3 font-mono text-xs text-zinc-500">{s.code}</td>
                <td className="px-6 py-3">{s.total}</td>
                <td className="px-6 py-3 text-blue-600">{s.open}</td>
                <td className="px-6 py-3 text-emerald-600">{s.resolved}</td>
                <td className="px-6 py-3">{s.active ? <span className="text-emerald-600">Active</span> : <span className="text-red-500">Inactive</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
const NoData = () => <div className="flex h-40 items-center justify-center text-sm text-zinc-400">No data yet</div>;
