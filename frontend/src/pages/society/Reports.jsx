import { PageHeader } from "@/components/Layout";
import { StatCard } from "@/components/StatCard";
import { useFetch } from "@/lib/useScope";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { Loader2, Ticket, CheckCircle2, Bot, Clock } from "lucide-react";

export default function Reports() {
  const { data, loading } = useFetch("/society/reports");
  if (loading || !data) return <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-zinc-400" /></div>;
  const { daily, categories, resolution, vendor_performance, summary } = data;

  return (
    <div className="p-8">
      <PageHeader title="Reports & Analytics" subtitle="Society Insights" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard testid="rep-total" label="Total Complaints" value={summary.total} icon={Ticket} />
        <StatCard testid="rep-resolved" label="Resolved" value={summary.resolved} icon={CheckCircle2} accent="text-emerald-600" />
        <StatCard testid="rep-ai" label="AI Detection Rate" value={`${summary.ai_detection_rate}%`} icon={Bot} accent="text-sky-600" />
        <StatCard testid="rep-aigen" label="AI Generated" value={summary.ai_generated} icon={Bot} />
      </div>

      <div className="mt-6 rounded-lg border border-border bg-card p-6">
        <p className="overline mb-4">Daily Complaints (last 14 days)</p>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={daily}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ border: "1px solid #e4e4e7", borderRadius: 8, fontSize: 12 }} />
            <Line type="monotone" dataKey="count" stroke="#18181B" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-6">
          <p className="overline mb-4">Category-wise</p>
          {categories.length === 0 ? <NoData /> : (
            <ResponsiveContainer width="100%" height={260}>
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
          <p className="overline mb-4">Avg Resolution Time (hrs)</p>
          {resolution.length === 0 ? <NoData /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={resolution}>
                <XAxis dataKey="category" tick={{ fontSize: 10 }} angle={-25} textAnchor="end" height={60} interval={0} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ border: "1px solid #e4e4e7", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="hours" fill="#0284C7" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-lg border border-border bg-card">
        <p className="overline border-b border-border px-6 py-4">Vendor Performance</p>
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-secondary/50 text-left text-[11px] uppercase tracking-wider text-zinc-500">
            <tr><th className="px-6 py-3 font-medium">Vendor</th><th className="px-6 py-3 font-medium">Assigned</th><th className="px-6 py-3 font-medium">Resolved</th><th className="px-6 py-3 font-medium">Rate</th></tr>
          </thead>
          <tbody>
            {vendor_performance.length === 0 ? <tr><td colSpan={4} className="py-10 text-center text-sm text-zinc-400">No data</td></tr> :
              vendor_performance.map((v, i) => (
                <tr key={i} className="border-b border-border last:border-0 hover:bg-secondary/50">
                  <td className="px-6 py-3 font-medium">{v.vendor}</td>
                  <td className="px-6 py-3">{v.assigned}</td>
                  <td className="px-6 py-3 text-emerald-600">{v.resolved}</td>
                  <td className="px-6 py-3">{v.rate}%</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
const NoData = () => <div className="flex h-40 items-center justify-center text-sm text-zinc-400">No data yet</div>;
