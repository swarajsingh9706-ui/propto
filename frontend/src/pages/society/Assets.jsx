import { useEffect, useMemo, useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope, useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { DashStat } from "@/components/DashKit";
import { StatusBadge, PriorityBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import {
  Plus, Loader2, Package, Trash2, Eye, Pencil, CheckCircle2, Ticket, CalendarClock,
  MoreVertical, ShieldAlert, AlertTriangle,
} from "lucide-react";

const TYPES = ["Lift", "Generator", "Water System", "Pump", "Fire Safety", "HVAC", "CCTV", "Gate", "Other"];
const FREQS = ["None", "Monthly", "Two Months", "Three Months", "Six Months", "Yearly"];
const BADGE = {
  "Due Soon": ["#fffbeb", "#d97706", "#fde68a", "Due Soon"],
  Overdue: ["#fef2f2", "#dc2626", "#fecaca", "Overdue"],
  Scheduled: ["#dcfce7", "#16a34a", "#86efac", "Scheduled"],
  Unscheduled: ["#f1f5f9", "#64748b", "#e2e8f0", "⚠ Not Scheduled"],
};
const emptyForm = { name: "", type: "Lift", location: "", next_service: "", service_frequency: "None", vendor_id: "none", notes: "" };

function Badge({ s }) {
  const [bg, fg, br, label] = BADGE[s] || BADGE.Scheduled;
  return <span data-testid="asset-status-badge" className="whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11px] font-bold" style={{ background: bg, color: fg, border: `1px solid ${br}` }}>{label}</span>;
}
const today = () => new Date().toISOString().slice(0, 10);

export default function Assets() {
  const cfg = useScope();
  const { data, loading, reload } = useFetch("/society/assets");
  const [tab, setTab] = useState("assets");
  const [vendors, setVendors] = useState([]);
  const [committee, setCommittee] = useState([]);
  const [tickets, setTickets] = useState([]);

  // dialogs
  const [fe, setFe] = useState({ open: false, mode: "add", id: null, form: emptyForm });
  const [svc, setSvc] = useState(null);      // { asset, service_date, service_frequency }
  const [sch, setSch] = useState(null);      // { asset, next_service, service_frequency, vendor_id }
  const [tk, setTk] = useState(null);        // { asset, priority, category, description }
  const [view, setView] = useState(null);
  const [mx, setMx] = useState(null);        // matrix array or null (closed)
  const [saving, setSaving] = useState(false);

  const assets = data || [];
  const c = useMemo(() => ({
    total: assets.length,
    due: assets.filter((a) => a.status === "Due Soon").length,
    over: assets.filter((a) => a.status === "Overdue").length,
    uns: assets.filter((a) => a.status === "Unscheduled").length,
  }), [assets]);

  useEffect(() => {
    api.get("/society/vendors", cfg).then((r) => setVendors(r.data)).catch(() => {});
    api.get("/society/committee", cfg).then((r) => setCommittee(r.data)).catch(() => {});
    // eslint-disable-next-line
  }, []);
  useEffect(() => {
    if (tab === "tickets") api.get("/society/assets/tickets", cfg).then((r) => setTickets(r.data)).catch(() => {});
    // eslint-disable-next-line
  }, [tab]);

  const vName = (id) => vendors.find((v) => v.id === id)?.name || "";
  const payloadFreq = (f) => (f === "None" ? "" : f);

  const saveForm = async () => {
    setSaving(true);
    const f = fe.form;
    const body = { name: f.name, type: f.type, location: f.location, next_service: f.next_service,
      service_frequency: payloadFreq(f.service_frequency), notes: f.notes,
      vendor_id: f.vendor_id === "none" ? "" : f.vendor_id, vendor_name: f.vendor_id === "none" ? "" : vName(f.vendor_id) };
    try {
      if (fe.mode === "add") await api.post("/society/assets", body, cfg);
      else await api.put(`/society/assets/${fe.id}`, body, cfg);
      toast.success(fe.mode === "add" ? "Asset added" : "Asset updated");
      setFe({ open: false, mode: "add", id: null, form: emptyForm }); reload();
    } catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const openEdit = (a) => setFe({ open: true, mode: "edit", id: a.id, form: {
    name: a.name || "", type: a.type || "Lift", location: a.location || "", next_service: a.next_service || "",
    service_frequency: a.service_frequency || "None", vendor_id: a.vendor_id || "none", notes: a.notes || "" } });

  const doService = async () => {
    setSaving(true);
    try {
      await api.post(`/society/assets/${svc.asset.id}/service-done`, { service_date: svc.service_date, service_frequency: payloadFreq(svc.service_frequency) }, cfg);
      toast.success("Service marked done"); setSvc(null); reload();
    } catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const doSchedule = async () => {
    setSaving(true);
    try {
      await api.post(`/society/assets/${sch.asset.id}/schedule`, { next_service: sch.next_service, service_frequency: payloadFreq(sch.service_frequency), vendor_id: sch.vendor_id === "none" ? "" : sch.vendor_id, vendor_name: sch.vendor_id === "none" ? "" : vName(sch.vendor_id) }, cfg);
      toast.success("Service scheduled"); setSch(null); reload();
    } catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const doTicket = async () => {
    setSaving(true);
    try {
      await api.post(`/society/assets/${tk.asset.id}/raise-ticket`, { priority: tk.priority, category: tk.category, description: tk.description }, cfg);
      toast.success("Ticket raised (assign it manually in Tickets)"); setTk(null);
      if (tab === "tickets") api.get("/society/assets/tickets", cfg).then((r) => setTickets(r.data));
    } catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const del = async (a) => { try { await api.delete(`/society/assets/${a.id}`); reload(); toast.success("Removed"); } catch (e) { toast.error(apiError(e)); } };

  // Escalation matrix
  const openMatrix = async () => {
    try { const { data: r } = await api.get("/society/escalation-matrix", cfg); setMx(r.matrix.length ? r.matrix : []); }
    catch (e) { toast.error(apiError(e)); }
  };
  const saveMatrix = async () => {
    setSaving(true);
    try { await api.put("/society/escalation-matrix", { matrix: mx }, cfg); toast.success("Escalation matrix saved"); setMx(null); }
    catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };

  const fmtDT = (s) => { const d = new Date(s); return isNaN(d) ? "—" : d.toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric" }); };

  return (
    <div className="p-4 sm:p-6 lg:p-8" data-testid="assets-page">
      <PageHeader title="Assets" subtitle="Asset Register">
        <Button data-testid="escalation-matrix-btn" variant="outline" onClick={openMatrix}><ShieldAlert className="mr-1.5 h-4 w-4" />Escalation Matrix</Button>
        <Button data-testid="add-asset-btn" onClick={() => setFe({ open: true, mode: "add", id: null, form: emptyForm })}><Plus className="mr-1.5 h-4 w-4" />Add Asset</Button>
      </PageHeader>

      <div className="mb-4 flex flex-wrap gap-2.5">
        <DashStat testid="asset-stat-total" value={c.total} label="Total Assets" sub="In register" color="#2563eb" icon={Package} iconBg="#dbeafe" />
        <DashStat testid="asset-stat-due" value={c.due} label="Due Soon" sub="Within 7 days" color="#d97706" icon={CalendarClock} iconBg="#fef3c7" />
        <DashStat testid="asset-stat-over" value={c.over} label="Overdue" sub="Past service date" color="#dc2626" icon={AlertTriangle} iconBg="#fee2e2" />
        <DashStat testid="asset-stat-uns" value={c.uns} label="Not Scheduled" sub="No service date" color="#64748b" icon={ShieldAlert} iconBg="#f1f5f9" />
      </div>

      <div className="mb-4 flex gap-2 border-b border-border">
        <button data-testid="tab-all-assets" onClick={() => setTab("assets")} className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${tab === "assets" ? "border-brand text-brand" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>All Assets</button>
        <button data-testid="tab-asset-tickets" onClick={() => setTab("tickets")} className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${tab === "tickets" ? "border-brand text-brand" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>Asset Tickets</button>
      </div>

      {tab === "assets" ? (
        <div className="overflow-hidden rounded-xl border border-border bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <div className="grid grid-cols-[1.4fr_1fr_1.1fr_1fr_1fr_1.2fr_44px] gap-2.5 border-b border-border bg-slate-50 px-[18px] py-2">
            {["ASSET", "TYPE", "LOCATION", "NEXT SERVICE", "STATUS", "VENDOR", ""].map((h, i) => <div key={i} className="text-[10px] font-extrabold uppercase tracking-wide text-slate-400">{h}</div>)}
          </div>
          {loading ? <div className="p-6"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div> :
            assets.length === 0 ? <div className="p-10 text-center text-sm text-slate-400"><Package className="mx-auto mb-2 h-8 w-8 text-slate-300" />No assets yet. Add your first asset.</div> :
              assets.map((a, i) => (
                <div key={a.id} data-testid={`asset-row-${a.id}`} className="grid grid-cols-[1.4fr_1fr_1.1fr_1fr_1fr_1.2fr_44px] items-center gap-2.5 border-b border-border px-[18px] py-3"
                  style={{ background: i % 2 ? "#f8fafc" : "#fff", borderLeft: a.status === "Overdue" ? "3px solid #dc2626" : a.status === "Due Soon" ? "3px solid #d97706" : "3px solid transparent" }}>
                  <div className="text-[13px] font-bold text-slate-900">{a.name}</div>
                  <div className="text-[13px] text-slate-500">{a.type || "—"}</div>
                  <div className="text-[12px] text-slate-500">{a.location || "—"}</div>
                  <div className="text-[13px] text-slate-700">{a.next_service || "—"}</div>
                  <div><Badge s={a.status} /></div>
                  <div className="truncate text-[12px] text-slate-500">{a.vendor_name || "—"}</div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button data-testid={`asset-actions-${a.id}`} className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100"><MoreVertical className="h-4 w-4" /></button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <DropdownMenuItem data-testid={`asset-view-${a.id}`} onClick={() => setView(a)}><Eye className="mr-2 h-4 w-4" />View Details</DropdownMenuItem>
                      <DropdownMenuItem data-testid={`asset-edit-${a.id}`} onClick={() => openEdit(a)}><Pencil className="mr-2 h-4 w-4" />Edit</DropdownMenuItem>
                      <DropdownMenuItem data-testid={`asset-service-${a.id}`} onClick={() => setSvc({ asset: a, service_date: today(), service_frequency: a.service_frequency || "None" })}><CheckCircle2 className="mr-2 h-4 w-4" />Mark Service Done</DropdownMenuItem>
                      <DropdownMenuItem data-testid={`asset-schedule-${a.id}`} onClick={() => setSch({ asset: a, next_service: a.next_service || "", service_frequency: a.service_frequency || "None", vendor_id: a.vendor_id || "none" })}><CalendarClock className="mr-2 h-4 w-4" />Schedule Service</DropdownMenuItem>
                      <DropdownMenuItem data-testid={`asset-ticket-${a.id}`} onClick={() => setTk({ asset: a, priority: "Medium", category: a.type || "Maintenance", description: "" })}><Ticket className="mr-2 h-4 w-4" />Raise Ticket</DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem data-testid={`asset-delete-${a.id}`} onClick={() => del(a)} className="text-red-600"><Trash2 className="mr-2 h-4 w-4" />Delete</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ))}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]" data-testid="asset-tickets-table">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="border-b border-border bg-slate-50 text-left text-[11px] uppercase tracking-wider text-slate-400">
              <tr><th className="px-5 py-3 font-medium">Ticket</th><th className="px-5 py-3 font-medium">Asset</th><th className="px-5 py-3 font-medium">Issue</th><th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Priority</th><th className="px-5 py-3 font-medium">Raised</th></tr>
            </thead>
            <tbody>
              {tickets.length === 0 ? <tr><td colSpan={6} className="py-12 text-center text-sm text-slate-400"><Ticket className="mx-auto mb-2 h-8 w-8 text-slate-300" />No asset tickets yet. Use "Raise Ticket" on an asset.</td></tr> :
                tickets.map((t) => (
                  <tr key={t.id} data-testid={`asset-ticket-row-${t.id}`} className="border-b border-border last:border-0 hover:bg-slate-50">
                    <td className="px-5 py-3 font-mono text-xs font-semibold text-brand">{t.ticket_number}</td>
                    <td className="px-5 py-3 font-medium">{t.asset_name || "—"}</td>
                    <td className="px-5 py-3 text-zinc-600">{t.description}</td>
                    <td className="px-5 py-3"><StatusBadge status={t.status} /></td>
                    <td className="px-5 py-3"><PriorityBadge priority={t.priority} /></td>
                    <td className="px-5 py-3 whitespace-nowrap text-xs text-zinc-500">{fmtDT(t.created_at)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add / Edit dialog */}
      <Dialog open={fe.open} onOpenChange={(o) => !o && setFe((s) => ({ ...s, open: false }))}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-cabinet">{fe.mode === "add" ? "New Asset" : "Edit Asset"}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div><Label className="text-xs">Name</Label><Input data-testid="asset-name-input" value={fe.form.name} onChange={(e) => setFe((s) => ({ ...s, form: { ...s.form, name: e.target.value } }))} className="mt-1" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Type</Label>
                <Select value={fe.form.type} onValueChange={(v) => setFe((s) => ({ ...s, form: { ...s.form, type: v } }))}><SelectTrigger data-testid="asset-type-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent>{TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select>
              </div>
              <div><Label className="text-xs">Location</Label><Input data-testid="asset-location-input" value={fe.form.location} onChange={(e) => setFe((s) => ({ ...s, form: { ...s.form, location: e.target.value } }))} className="mt-1" placeholder="Tower B" /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Next Service Date</Label><Input data-testid="asset-service-input" type="date" value={fe.form.next_service} onChange={(e) => setFe((s) => ({ ...s, form: { ...s.form, next_service: e.target.value } }))} className="mt-1" /></div>
              <div><Label className="text-xs">Service Frequency</Label>
                <Select value={fe.form.service_frequency} onValueChange={(v) => setFe((s) => ({ ...s, form: { ...s.form, service_frequency: v } }))}><SelectTrigger data-testid="asset-frequency-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent>{FREQS.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent></Select>
              </div>
            </div>
            <div><Label className="text-xs">Assigned Vendor (for service alerts)</Label>
              <Select value={fe.form.vendor_id} onValueChange={(v) => setFe((s) => ({ ...s, form: { ...s.form, vendor_id: v } }))}><SelectTrigger data-testid="asset-vendor-select" className="mt-1"><SelectValue placeholder="None" /></SelectTrigger><SelectContent><SelectItem value="none">None</SelectItem>{vendors.map((v) => <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>)}</SelectContent></Select>
            </div>
            <div><Label className="text-xs">Notes</Label><Textarea data-testid="asset-notes-input" value={fe.form.notes} onChange={(e) => setFe((s) => ({ ...s, form: { ...s.form, notes: e.target.value } }))} className="mt-1" rows={2} /></div>
          </div>
          <DialogFooter><Button data-testid="save-asset-btn" onClick={saveForm} disabled={saving || !fe.form.name}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{fe.mode === "add" ? "Add Asset" : "Save Changes"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View details */}
      <Dialog open={!!view} onOpenChange={(o) => !o && setView(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle className="font-cabinet">{view?.name}</DialogTitle></DialogHeader>
          {view && (
            <div className="space-y-2 text-sm">
              <Row label="Type" value={view.type || "—"} />
              <Row label="Location" value={view.location || "—"} />
              <Row label="Status" value={<Badge s={view.status} />} />
              <Row label="Last Service" value={view.last_service || "—"} />
              <Row label="Next Service" value={view.next_service || "—"} />
              <Row label="Frequency" value={view.service_frequency || "Not set"} />
              <Row label="Vendor" value={view.vendor_name || "—"} />
              {view.notes && <div className="pt-1"><p className="text-xs text-zinc-400">Notes</p><p className="text-sm text-zinc-700">{view.notes}</p></div>}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Mark service done */}
      <Dialog open={!!svc} onOpenChange={(o) => !o && setSvc(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle className="font-cabinet">Mark Service Done</DialogTitle></DialogHeader>
          {svc && (
            <div className="space-y-3">
              <p className="text-sm text-zinc-500">Recording service for <b>{svc.asset.name}</b>.</p>
              <div><Label className="text-xs">Service Date</Label><Input data-testid="service-date-input" type="date" value={svc.service_date} onChange={(e) => setSvc({ ...svc, service_date: e.target.value })} className="mt-1" /></div>
              <div><Label className="text-xs">Repeat Every</Label>
                <Select value={svc.service_frequency} onValueChange={(v) => setSvc({ ...svc, service_frequency: v })}><SelectTrigger data-testid="service-frequency-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent>{FREQS.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent></Select>
                <p className="mt-1 text-[11px] text-zinc-400">Next service date is auto-scheduled from this date + frequency.</p>
              </div>
            </div>
          )}
          <DialogFooter><Button data-testid="confirm-service-btn" onClick={doService} disabled={saving}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Confirm</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Schedule service */}
      <Dialog open={!!sch} onOpenChange={(o) => !o && setSch(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle className="font-cabinet">Schedule Service</DialogTitle></DialogHeader>
          {sch && (
            <div className="space-y-3">
              <div><Label className="text-xs">Next Service Date</Label><Input data-testid="schedule-date-input" type="date" value={sch.next_service} onChange={(e) => setSch({ ...sch, next_service: e.target.value })} className="mt-1" /></div>
              <div><Label className="text-xs">Repeat Every</Label>
                <Select value={sch.service_frequency} onValueChange={(v) => setSch({ ...sch, service_frequency: v })}><SelectTrigger data-testid="schedule-frequency-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent>{FREQS.map((f) => <SelectItem key={f} value={f}>{f}</SelectItem>)}</SelectContent></Select>
              </div>
              <div><Label className="text-xs">Vendor</Label>
                <Select value={sch.vendor_id} onValueChange={(v) => setSch({ ...sch, vendor_id: v })}><SelectTrigger data-testid="schedule-vendor-select" className="mt-1"><SelectValue placeholder="None" /></SelectTrigger><SelectContent><SelectItem value="none">None</SelectItem>{vendors.map((v) => <SelectItem key={v.id} value={v.id}>{v.name}</SelectItem>)}</SelectContent></Select>
              </div>
            </div>
          )}
          <DialogFooter><Button data-testid="confirm-schedule-btn" onClick={doSchedule} disabled={saving || !sch?.next_service}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Schedule</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Raise ticket */}
      <Dialog open={!!tk} onOpenChange={(o) => !o && setTk(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle className="font-cabinet">Raise Ticket · {tk?.asset.name}</DialogTitle></DialogHeader>
          {tk && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Category</Label><Input data-testid="ticket-category-input" value={tk.category} onChange={(e) => setTk({ ...tk, category: e.target.value })} className="mt-1" /></div>
                <div><Label className="text-xs">Priority</Label>
                  <Select value={tk.priority} onValueChange={(v) => setTk({ ...tk, priority: v })}><SelectTrigger data-testid="ticket-priority-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent>{["Critical", "High", "Medium", "Low"].map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent></Select>
                </div>
              </div>
              <div><Label className="text-xs">Description</Label><Textarea data-testid="ticket-desc-input" value={tk.description} onChange={(e) => setTk({ ...tk, description: e.target.value })} className="mt-1" rows={3} placeholder="Describe the issue…" /></div>
              <p className="text-[11px] text-zinc-400">Ticket is created as <b>Open</b> — assign a vendor manually from the Tickets page.</p>
            </div>
          )}
          <DialogFooter><Button data-testid="confirm-ticket-btn" onClick={doTicket} disabled={saving}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Raise Ticket</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Escalation matrix */}
      <Dialog open={mx !== null} onOpenChange={(o) => !o && setMx(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-cabinet">Escalation Matrix</DialogTitle></DialogHeader>
          <p className="text-xs text-zinc-500">Service-due WhatsApp alerts go to the asset's vendor plus these contacts, in order. If left empty, alerts go to the vendor + Society Manager (Secretary/Manager/Chairman).</p>
          <div className="mt-3 space-y-2">
            {(mx || []).map((lvl, idx) => (
              <div key={idx} data-testid={`matrix-level-${idx}`} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand/10 text-xs font-bold text-brand">{idx + 1}</span>
                <Select value={lvl.phone || "custom"} onValueChange={(v) => {
                  const m = committee.find((c2) => c2.phone === v);
                  setMx((arr) => arr.map((x, i) => i === idx ? (m ? { ...x, name: m.name, phone: m.phone, role: m.role } : x) : x));
                }}>
                  <SelectTrigger data-testid={`matrix-contact-${idx}`} className="h-8 w-[180px] text-xs"><SelectValue placeholder="Select member" /></SelectTrigger>
                  <SelectContent>{committee.map((cm) => <SelectItem key={cm.id} value={cm.phone || cm.id}>{cm.name} · {cm.role}</SelectItem>)}</SelectContent>
                </Select>
                <span className="text-xs text-zinc-500">{lvl.name || "—"}</span>
                <div className="ml-auto flex items-center gap-1">
                  <Input type="number" min="0" data-testid={`matrix-wait-${idx}`} value={lvl.wait_minutes} onChange={(e) => setMx((arr) => arr.map((x, i) => i === idx ? { ...x, wait_minutes: e.target.value } : x))} className="h-8 w-16 text-xs" />
                  <span className="text-[11px] text-zinc-400">min wait</span>
                  <button data-testid={`matrix-remove-${idx}`} onClick={() => setMx((arr) => arr.filter((_, i) => i !== idx))} className="text-zinc-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
            ))}
            <Button data-testid="matrix-add-level" variant="outline" size="sm" onClick={() => setMx((arr) => [...(arr || []), { name: "", phone: "", role: "", wait_minutes: 15 }])}><Plus className="mr-1.5 h-3.5 w-3.5" />Add Level</Button>
          </div>
          <DialogFooter><Button data-testid="save-matrix-btn" onClick={saveMatrix} disabled={saving}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Save Matrix</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const Row = ({ label, value }) => (
  <div className="flex justify-between border-b border-border pb-2"><span className="text-zinc-400">{label}</span><span className="text-right font-medium text-zinc-800">{value}</span></div>
);
