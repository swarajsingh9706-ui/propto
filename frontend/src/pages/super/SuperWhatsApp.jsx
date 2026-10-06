import { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import WhatsApp from "@/pages/society/WhatsApp";
import { Loader2, MessageSquare, Search, ArrowLeft } from "lucide-react";

export default function SuperWhatsApp() {
  const [societies, setSocieties] = useState([]);
  const [sel, setSel] = useState(null);
  const [query, setQuery] = useState("");
  const [cityFilter, setCityFilter] = useState("all");

  useEffect(() => {
    api.get("/super/societies").then((r) => setSocieties(r.data)).catch(() => {});
  }, []);

  const cities = Array.from(new Set(societies.map((s) => s.city).filter(Boolean)));
  const filtered = societies.filter((s) => {
    if (cityFilter !== "all" && s.city !== cityFilter) return false;
    const q = query.trim().toLowerCase();
    if (q && !(`${s.name} ${s.code} ${s.city || ""}`.toLowerCase().includes(q))) return false;
    return true;
  });
  const current = societies.find((s) => s.id === sel);

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="WhatsApp Integration" subtitle="Super Admin" />

      {!sel ? (
        <>
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
              <Input data-testid="wa-society-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search society by name, code or city…" className="pl-9" />
            </div>
            <Select value={cityFilter} onValueChange={setCityFilter}>
              <SelectTrigger data-testid="wa-city-filter" className="w-48"><SelectValue placeholder="All locations" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Locations</SelectItem>
                {cities.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {societies.length === 0 ? (
            <div className="rounded-lg border border-dashed border-border bg-card p-12 text-center text-sm text-zinc-500">
              <MessageSquare className="mx-auto mb-3 h-8 w-8 text-zinc-300" />No societies yet. Add a society first to configure WhatsApp.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {filtered.map((s) => {
                const connected = !!(s.whatsapp_group && s.monitoring);
                return (
                <button key={s.id} data-testid={`wa-society-${s.code}`} onClick={() => setSel(s.id)}
                  className="card-hover flex items-center gap-3 rounded-lg border border-border bg-card p-4 text-left">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-secondary"><MessageSquare className="h-5 w-5 text-zinc-700" /></div>
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate font-cabinet text-base font-bold tracking-tight">{s.name}</h3>
                    <p className="text-xs text-zinc-400">{s.code} · {s.city || "—"}</p>
                  </div>
                  <span data-testid={`wa-status-${s.code}`}
                    className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-bold ${
                      connected ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-zinc-200 bg-zinc-100 text-zinc-600"}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-zinc-400"}`} />
                    {connected ? "Active" : "Disabled"}
                  </span>
                </button>
                );
              })}
            </div>
          )}
        </>
      ) : (
        <div>
          <button data-testid="wa-back" onClick={() => setSel(null)} className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-brand hover:underline">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to societies
          </button>
          <p className="mb-4 text-xs text-zinc-400">Configuring WhatsApp for <span className="font-medium text-brand">{current?.name}</span></p>
          <WhatsApp societyId={sel} embedded key={sel} />
        </div>
      )}
    </div>
  );
}
