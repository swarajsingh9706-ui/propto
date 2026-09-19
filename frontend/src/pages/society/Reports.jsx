import { useEffect, useState } from "react";
import api from "@/lib/api";
import { useScope } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { StatCard } from "@/components/StatCard";
import { DateRangeFilter } from "@/components/DateRangeFilter";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { Loader2, Ticket, CheckCircle2, Bot } from "lucide-react";

export default function Reports() {
  const cfg = useScope();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState({ start: "", end: "" });

  useEffect(() => {
    setLoading(true);
    const params = { ...cfg.params };
    if (range.start) params.start = range.start;
    if (range.end) params.end = range.end;
    api.get("/society/reports", { params })
      .then((r) => setData(r.data))
      .finally(() => setLoading(false));
    // eslint-disable-next-line
  }, [range, cfg.params?.society_id]);

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Reports & Analytics" subtitle="Society Insights">
        <DateRangeFilter onChange={setRange} testidPrefix="reports-range" />
      </PageHeader>

      {loading || !data ? (
        <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-zinc-400" /></div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard testid="rep-total" label="Total Complaints" value={data.summary.total} icon={Ticket} />
            <StatCard testid="rep-resolved" label="Resolved" value={data.summary.resolved} icon={CheckCircle2} accent="text-emerald-600" />
            <StatCard testid="rep-ai" label="AI Detection Rate" value={`${data.summary.ai_detection_rate}%`} icon={Bot} accent="text-sky-600" />
            <StatCard testid="rep-aigen" label="AI Generated" value={data.summary.ai_generated} icon={Bot} />
          </div>

          <div className="mt-6 rounded-lg border border-border bg-card p-6">
            <p className="overline mb-4">Daily Complaints</p>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={data.daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ border: "1px solid #e4e4e7", borderRadius: 8, fontSize: 12 }} />
                <Line type="monotone" dataKey="count" stroke="#0C4428" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-card p-6">
              <p className="overline mb-4">Top Issue Categories</p>
              {data.categories.length === 0 ? <NoData /> : (
                <div className="space-y-3.5">
                  {data.categories.slice(0, 8).map((c, i) => {
                    const max = data.categories[0].count || 1;
                    const pct = Math.round((c.count / max) * 100);
                    const bar = ["#2563eb", "#4f46e5", "#06b6d4", "#22c55e", "#f59e0b", "#8b5cf6", "#ec4899", "#14b8a6"][i % 8];
                    return (
                      <div key={c.category} data-testid={`report-cat-${i}`}>
                        <div className="mb-1.5 flex items-center justify-between text-[13px]">
                          <span className="truncate font-semibold text-slate-700">{c.category}</span>
                          <span className="font-bold text-slate-500">{c.count}</span>
                        </div>
                        <div className="h-2 rounded-full bg-slate-100">
                          <div className="h-2 rounded-full transition-all" style={{ width: `${pct}%`, background: bar }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="rounded-lg border border-border bg-card p-6">
              <p className="overline mb-4">Avg Resolution Time (hrs)</p>
              {data.resolution.length === 0 ? <NoData /> : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={data.resolution}>
                    <XAxis dataKey="category" tick={{ fontSize: 10 }} angle={-25} textAnchor="end" height={60} interval={0} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip contentStyle={{ border: "1px solid #e4e4e7", borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="hours" fill="#C6A02C" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="mt-6 overflow-x-auto rounded-lg border border-border bg-card">
            <p className="overline border-b border-border px-6 py-4">Vendor Performance</p>
            <table className="w-full min-w-[520px] text-sm">
              <thead className="border-b border-border bg-secondary/50 text-left text-[11px] uppercase tracking-wider text-zinc-500">
                <tr><th className="px-6 py-3 font-medium">Vendor</th><th className="px-6 py-3 font-medium">Assigned</th><th className="px-6 py-3 font-medium">Resolved</th><th className="px-6 py-3 font-medium">Rate</th></tr>
              </thead>
              <tbody>
                {data.vendor_performance.length === 0 ? <tr><td colSpan={4} className="py-10 text-center text-sm text-zinc-400">No data</td></tr> :
                  data.vendor_performance.map((v, i) => (
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
        </>
      )}
    </div>
  );
}
const NoData = () => <div className="flex h-40 items-center justify-center text-sm text-zinc-400">No data yet</div>;
