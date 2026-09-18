import { useEffect, useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { StatusBadge, PriorityBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import { toast } from "sonner";
import { Search, Loader2, Bot, CheckCircle2, UserPlus, Clock, Flame } from "lucide-react";

const CATEGORIES = ["Plumbing", "Electrical", "Lift", "Security", "Housekeeping", "Civil", "Parking", "Gardening", "Water Supply", "DG Set", "Pest Control"];
const STATUSES = ["all", "Open", "Pending", "Resolved", "Escalated", "Closed"];

const fmtDT = (s) => {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d)) return "—";
  return d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
};

const FilterPill = ({ active, onClick, children, testid }) => (
  <button
    type="button"
    data-testid={testid}
    onClick={onClick}
    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
      active ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-zinc-600 hover:bg-secondary"
    }`}
  >
    {children}
  </button>
);

export default function Tickets() {
  const cfg = useScope();
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [category, setCategory] = useState("all");
  const [priority, setPriority] = useState("all");
  const [selected, setSelected] = useState(null);
  const [vendors, setVendors] = useState([]);
  const [pendingVendor, setPendingVendor] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/society/tickets", { params: { ...cfg.params, status, category, priority, search } });
      setTickets(data);
    } catch (e) { toast.error(apiError(e)); }
    finally { setLoading(false); }
  };
  // Single debounced loader for all filters. The cleanup cancels the pending
  // fetch, so React StrictMode's double-invoke (dev) collapses to one call — no flicker.
  useEffect(() => {
    const t = setTimeout(load, search ? 400 : 0);
    return () => clearTimeout(t);
    /* eslint-disable-next-line */
  }, [status, category, priority, search]);
  useEffect(() => { api.get("/society/vendors", cfg).then((r) => setVendors(r.data)); /* eslint-disable-next-line */ }, []);

  const openTicket = async (t) => {
    const { data } = await api.get(`/society/tickets/${t.id}`);
    setSelected(data);
    setPendingVendor(data.vendor_id || "");
  };
  const assign = async (vendorId) => {
    try {
      const { data } = await api.post(`/society/tickets/${selected.id}/assign`, { vendor_id: vendorId });
      setSelected(data); load(); toast.success("Vendor assigned");
    } catch (e) { toast.error(apiError(e)); }
  };
  const setStatusVal = async (val) => {
    try {
      const { data } = await api.put(`/society/tickets/${selected.id}`, { status: val });
      setSelected(data); load(); toast.success(`Marked ${val}`);
    } catch (e) { toast.error(apiError(e)); }
  };
  const close = async () => {
    try {
      const { data } = await api.post(`/society/tickets/${selected.id}/close`);
      setSelected(data); load(); toast.success("Ticket resolved");
    } catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Complaint Management" subtitle="Tickets" />

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <Input data-testid="ticket-search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search ticket, flat, resident…" className="pl-9" />
        </div>
        <Button
          data-testid="filter-priority-high"
          type="button"
          variant={priority === "High" ? "default" : "outline"}
          onClick={() => setPriority((p) => (p === "High" ? "all" : "High"))}
        >
          <Flame className="mr-1.5 h-4 w-4" />High Priority
        </Button>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger data-testid="filter-status" className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            {STATUSES.map((s) => <SelectItem key={s} value={s}>{s === "all" ? "All Status" : s}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger data-testid="filter-category" className="w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="mr-1 text-[11px] font-medium uppercase tracking-wider text-zinc-400">Status</span>
        {STATUSES.map((s) => (
          <FilterPill key={s} testid={`pill-status-${s}`} active={status === s} onClick={() => setStatus(s)}>
            {s === "all" ? "All" : s}
          </FilterPill>
        ))}
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="mr-1 text-[11px] font-medium uppercase tracking-wider text-zinc-400">Category</span>
        <FilterPill testid="pill-category-all" active={category === "all"} onClick={() => setCategory("all")}>All</FilterPill>
        {CATEGORIES.map((c) => (
          <FilterPill key={c} testid={`pill-category-${c}`} active={category === c} onClick={() => setCategory(c)}>{c}</FilterPill>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-card">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="border-b border-border bg-secondary/50 text-left">
            <tr className="text-[11px] uppercase tracking-wider text-zinc-500">
              <th className="px-5 py-3 font-medium">Ticket</th>
              <th className="px-5 py-3 font-medium">Category</th>
              <th className="px-5 py-3 font-medium">Flat</th>
              <th className="px-5 py-3 font-medium">Priority</th>
              <th className="px-5 py-3 font-medium">Resident</th>
              <th className="px-5 py-3 font-medium">Vendor</th>
              <th className="px-5 py-3 font-medium">Status</th>
              <th className="px-5 py-3 font-medium">Date &amp; Time</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="py-16 text-center"><Loader2 className="mx-auto h-6 w-6 animate-spin text-zinc-400" /></td></tr>
            ) : tickets.length === 0 ? (
              <tr><td colSpan={8} className="py-16 text-center text-sm text-zinc-400">No tickets found</td></tr>
            ) : tickets.map((t) => (
              <tr key={t.id} data-testid={`ticket-row-${t.ticket_number}`} onClick={() => openTicket(t)} className="cursor-pointer border-b border-border last:border-0 hover:bg-secondary/50">
                <td className="px-5 py-3 font-mono text-xs text-zinc-600">{t.ticket_number}</td>
                <td className="px-5 py-3 font-medium">{t.category}</td>
                <td className="px-5 py-3 text-zinc-500">{t.flat || "—"}</td>
                <td className="px-5 py-3"><PriorityBadge priority={t.priority} /></td>
                <td className="px-5 py-3 text-zinc-600" data-testid={`ticket-resident-${t.ticket_number}`}>{t.resident_name || <span className="text-zinc-300">Unknown</span>}</td>
                <td className="px-5 py-3 text-zinc-500">{t.vendor_name || <span className="text-zinc-300">Unassigned</span>}</td>
                <td className="px-5 py-3"><StatusBadge status={t.status} /></td>
                <td className="px-5 py-3 whitespace-nowrap text-xs text-zinc-500" data-testid={`ticket-date-${t.ticket_number}`}>{fmtDT(t.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Sheet open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-md">
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle className="font-cabinet flex items-center gap-2">
                  {selected.ticket_number}
                  {selected.ai_generated && <Bot className="h-4 w-4 text-sky-600" />}
                </SheetTitle>
              </SheetHeader>
              <div className="mt-4 space-y-4">
                <div className="flex gap-2"><StatusBadge status={selected.status} /><PriorityBadge priority={selected.priority} /></div>
                <Row label="Category" value={selected.category} />
                <Row label="Flat / Tower" value={`${selected.flat || "—"} ${selected.tower ? "· " + selected.tower : ""}`} />
                <Row label="Resident" value={`${selected.resident_name} · ${selected.resident_phone || "—"}`} />
                <Row label="Preferred Time" value={selected.preferred_time || "—"} />
                <div>
                  <p className="overline mb-1">Description</p>
                  <p className="text-sm text-zinc-700">{selected.description}</p>
                </div>
                {selected.raw_message && (
                  <div className="rounded-md bg-secondary p-3">
                    <p className="overline mb-1">Original Message</p>
                    <p className="text-xs italic text-zinc-500">"{selected.raw_message}"</p>
                    {selected.ai_confidence != null && <p className="mt-1 text-[11px] text-sky-600">AI confidence: {(selected.ai_confidence * 100).toFixed(0)}%</p>}
                  </div>
                )}

                <div>
                  <p className="overline mb-2">Assign / Reassign Vendor</p>
                  <Select onValueChange={setPendingVendor} value={pendingVendor || ""}>
                    <SelectTrigger data-testid="assign-vendor-select"><SelectValue placeholder="Select vendor" /></SelectTrigger>
                    <SelectContent>
                      {vendors.filter((v) => v.categories?.includes(selected.category)).map((v) => (
                        <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>
                      ))}
                      {vendors.filter((v) => !v.categories?.includes(selected.category)).map((v) => (
                        <SelectItem key={v.id} value={v.id}>{v.name} (other)</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    data-testid="assign-vendor-confirm"
                    size="sm"
                    className="mt-2 w-full"
                    disabled={!pendingVendor || pendingVendor === selected.vendor_id}
                    onClick={() => assign(pendingVendor)}
                  >
                    <UserPlus className="mr-1.5 h-3.5 w-3.5" />
                    {selected.vendor_id ? "Reassign Vendor" : "Assign Vendor"}
                  </Button>
                </div>

                <div className="flex flex-wrap gap-2 pt-2">
                  <Button data-testid="ticket-escalate-btn" size="sm" variant="outline" onClick={() => setStatusVal("Escalated")}>Escalate</Button>
                  <Button data-testid="ticket-pending-btn" size="sm" variant="outline" onClick={() => setStatusVal("Pending")}><Clock className="mr-1 h-3.5 w-3.5" />Pending</Button>
                  <Button data-testid="ticket-close-btn" size="sm" onClick={close}><CheckCircle2 className="mr-1 h-3.5 w-3.5" />Resolve</Button>
                </div>

                <div className="border-t border-border pt-4">
                  <p className="overline mb-3">Timeline</p>
                  <div className="space-y-3">
                    {(selected.timeline || []).map((ev, i) => (
                      <div key={i} className="flex gap-3">
                        <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-zinc-900" />
                        <div>
                          <p className="text-sm font-medium">{ev.event}</p>
                          {ev.detail && <p className="text-xs text-zinc-400">{ev.detail}</p>}
                          <p className="text-[10px] text-zinc-300">{new Date(ev.at).toLocaleString()}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

const Row = ({ label, value }) => (
  <div className="flex justify-between border-b border-border pb-2 text-sm">
    <span className="text-zinc-400">{label}</span><span className="font-medium text-zinc-800">{value}</span>
  </div>
);
