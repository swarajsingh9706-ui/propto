import { useMemo, useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope, useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { DashStat, Panel } from "@/components/DashKit";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Plus, Loader2, Package, Trash2 } from "lucide-react";

const TYPES = ["Lift", "Generator", "Water System", "Pump", "Fire Safety", "HVAC", "CCTV", "Gate", "Other"];
const STATUS = ["Scheduled", "Due Soon", "Overdue", "Serviced"];
const BADGE = {
  "Due Soon": ["#fffbeb", "#d97706", "#fde68a"],
  Overdue: ["#fef2f2", "#dc2626", "#fecaca"],
  Scheduled: ["#dcfce7", "#16a34a", "#86efac"],
  Serviced: ["#eff6ff", "#2563eb", "#bfdbfe"],
};
const empty = { name: "", type: "Lift", location: "", next_service: "", status: "Scheduled" };

function Badge({ s }) {
  const [bg, fg, br] = BADGE[s] || BADGE.Scheduled;
  return <span className="rounded-full px-2.5 py-0.5 text-[11px] font-bold" style={{ background: bg, color: fg, border: `1px solid ${br}` }}>{s}</span>;
}

export default function Assets() {
  const cfg = useScope();
  const { data, loading, reload } = useFetch("/society/assets");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const assets = data || [];
  const c = useMemo(() => ({
    total: assets.length,
    due: assets.filter((a) => a.status === "Due Soon").length,
    over: assets.filter((a) => a.status === "Overdue").length,
    sched: assets.filter((a) => a.status === "Scheduled").length,
  }), [assets]);

  const create = async () => {
    setSaving(true);
    try { await api.post("/society/assets", form, cfg); toast.success("Asset added"); setOpen(false); setForm(empty); reload(); }
    catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const del = async (a) => { try { await api.delete(`/society/assets/${a.id}`); reload(); toast.success("Removed"); } catch (e) { toast.error(apiError(e)); } };

  return (
    <div className="p-8" data-testid="assets-page">
      <PageHeader title="Assets" subtitle="Asset Register">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="add-asset-btn"><Plus className="mr-1.5 h-4 w-4" />Add Asset</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-cabinet">New Asset</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label className="text-xs">Name</Label><Input data-testid="asset-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" /></div>
              <div><Label className="text-xs">Type</Label>
                <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}><SelectTrigger data-testid="asset-type-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent>{TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select>
              </div>
              <div><Label className="text-xs">Location</Label><Input data-testid="asset-location-input" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className="mt-1" placeholder="Tower B, Basement" /></div>
              <div><Label className="text-xs">Next Service Date</Label><Input data-testid="asset-service-input" type="date" value={form.next_service} onChange={(e) => setForm({ ...form, next_service: e.target.value })} className="mt-1" /></div>
              <div><Label className="text-xs">Status</Label>
                <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}><SelectTrigger data-testid="asset-status-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent>{STATUS.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent></Select>
              </div>
            </div>
            <DialogFooter><Button data-testid="save-asset-btn" onClick={create} disabled={saving || !form.name}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Add Asset</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </PageHeader>

      <div className="mb-4 flex flex-wrap gap-2.5">
        <DashStat testid="asset-stat-total" value={c.total} label="Total Assets" sub="In register" color="#2563eb" icon={Package} iconBg="#dbeafe" />
        <DashStat testid="asset-stat-due" value={c.due} label="Due Soon" sub="Service upcoming" color="#d97706" icon={Package} iconBg="#fef3c7" />
        <DashStat testid="asset-stat-over" value={c.over} label="Overdue" sub="Past service date" color="#dc2626" icon={Package} iconBg="#fee2e2" />
        <DashStat testid="asset-stat-sched" value={c.sched} label="Scheduled" sub="On track" color="#16a34a" icon={Package} iconBg="#dcfce7" />
      </div>

      <Panel title="Asset Register" testid="assets-panel">
        <div className="grid grid-cols-[1.5fr_1fr_1.2fr_1fr_1fr_60px] gap-2.5 border-b border-border bg-slate-50 px-[18px] py-2">
          {["ASSET", "TYPE", "LOCATION", "NEXT SERVICE", "STATUS", ""].map((h, i) => <div key={i} className="text-[10px] font-extrabold uppercase tracking-wide text-slate-400">{h}</div>)}
        </div>
        {loading ? <div className="p-6"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div> :
          assets.length === 0 ? <div className="p-10 text-center text-sm text-slate-400"><Package className="mx-auto mb-2 h-8 w-8 text-slate-300" />No assets yet. Add your first asset.</div> :
            assets.map((a, i) => (
              <div key={a.id} data-testid={`asset-row-${a.id}`} className="grid grid-cols-[1.5fr_1fr_1.2fr_1fr_1fr_60px] items-center gap-2.5 border-b border-border px-[18px] py-3" style={{ background: i % 2 ? "#f8fafc" : "#fff" }}>
                <div className="text-[13px] font-bold text-slate-900">{a.name}</div>
                <div className="text-[13px] text-slate-500">{a.type || "—"}</div>
                <div className="text-[12px] text-slate-500">{a.location || "—"}</div>
                <div className="text-[13px] text-slate-700">{a.next_service || "—"}</div>
                <div><Badge s={a.status} /></div>
                <button data-testid={`delete-asset-${a.id}`} onClick={() => del(a)} className="text-slate-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
              </div>
            ))}
      </Panel>
    </div>
  );
}
