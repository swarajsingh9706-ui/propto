import { useEffect, useRef, useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope, useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Plus, Loader2, Trash2, Upload, Users, Search, Copy, Link2, Check, X, Pencil } from "lucide-react";
import { COUNTRY_CODES, splitPhone } from "@/lib/countryCodes";

const empty = { name: "", dial: "91", phone: "", flat: "", tower: "", status: "Owner" };

export default function Residents() {
  const cfg = useScope();
  const { data: residents, loading, reload } = useFetch("/society/residents");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [q, setQ] = useState("");
  const [statusF, setStatusF] = useState("all");
  const [tab, setTab] = useState("active");
  const [formUrl, setFormUrl] = useState("");
  const [busyId, setBusyId] = useState(null);
  const fileRef = useRef();

  useEffect(() => {
    api.get("/society/form-link", cfg)
      .then(({ data }) => setFormUrl(`${window.location.origin}${data.path}`))
      .catch(() => {});
    // eslint-disable-next-line
  }, [cfg.params?.society_id]);

  const create = async () => {
    setSaving(true);
    try {
      const payload = { name: form.name, phone: form.dial + (form.phone || "").replace(/\D/g, ""), flat: form.flat, tower: form.tower, status: form.status };
      await api.post("/society/residents", payload, cfg); toast.success("Resident added"); setOpen(false); setForm(empty); reload();
    }
    catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const del = async (r) => { try { await api.delete(`/society/residents/${r.id}`); reload(); } catch (e) { toast.error(apiError(e)); } };
  const openEdit = (r) => {
    const { dial, number } = splitPhone(r.phone || "");
    setEditing(r);
    setEditForm({ name: r.name || "", dial, phone: number, flat: r.flat || "", tower: r.tower || "", status: r.status || "Owner" });
  };
  const saveEdit = async () => {
    setSaving(true);
    try {
      const payload = { name: editForm.name, phone: editForm.dial + (editForm.phone || "").replace(/\D/g, ""), flat: editForm.flat, tower: editForm.tower, status: editForm.status };
      await api.put(`/society/residents/${editing.id}`, payload, cfg);
      toast.success("Resident updated"); setEditing(null); reload();
    } catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const reject = async (r) => {
    setBusyId(r.id);
    try { await api.delete(`/society/residents/${r.id}`); toast.success("Request rejected & removed"); reload(); }
    catch (e) { toast.error(apiError(e)); } finally { setBusyId(null); }
  };
  const approve = async (r) => {
    setBusyId(r.id);
    try {
      const { data } = await api.post(`/society/residents/${r.id}/approve`);
      if (data.invite?.sent) toast.success(`${r.name} approved — WhatsApp group invite sent`);
      else toast.success(`${r.name} approved (group invite could not be sent — WhatsApp not connected)`);
      reload();
    } catch (e) { toast.error(apiError(e)); } finally { setBusyId(null); }
  };
  const importFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    try {
      const { data } = await api.post("/society/residents/import", fd, { params: cfg.params, headers: { "Content-Type": "multipart/form-data" } });
      toast.success(`Imported ${data.inserted} residents`); reload();
    } catch (err) { toast.error(apiError(err)); }
    e.target.value = "";
  };
  const copyLink = () => { navigator.clipboard.writeText(formUrl); toast.success("Form link copied"); };

  const all = residents || [];
  const pending = all.filter((r) => r.approval === "pending");
  const active = all.filter((r) => r.approval !== "pending");
  const source = tab === "pending" ? pending : active;
  const filtered = source.filter((r) => {
    if (tab === "active" && statusF !== "all" && (r.status || "Owner") !== statusF) return false;
    if (q) {
      const s = q.toLowerCase();
      return [r.name, r.flat, r.tower, r.phone].some((x) => (x || "").toLowerCase().includes(s));
    }
    return true;
  });

  const SourceBadge = ({ r }) => (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${
      r.source === "form" ? "border-amber-200 bg-amber-50 text-amber-700" : "border-slate-200 bg-slate-50 text-slate-500"}`}>
      {r.source === "form" ? "Via Form" : r.source === "import" ? "Imported" : "Added"}
    </span>
  );

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Resident Management" subtitle="Residents">
        <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" onChange={importFile} className="hidden" data-testid="import-file-input" />
        <Button data-testid="import-residents-btn" variant="outline" onClick={() => fileRef.current?.click()}><Upload className="mr-1.5 h-4 w-4" />Import Excel</Button>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="add-resident-btn"><Plus className="mr-1.5 h-4 w-4" />Add Resident</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-cabinet">New Resident</DialogTitle></DialogHeader>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2"><Label className="text-xs">Name</Label><Input data-testid="resident-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" /></div>
              <div className="col-span-2"><Label className="text-xs">Phone</Label>
                <div className="mt-1 flex gap-2">
                  <Select value={form.dial} onValueChange={(v) => setForm({ ...form, dial: v })}>
                    <SelectTrigger data-testid="resident-country-code" className="w-[150px] shrink-0"><SelectValue /></SelectTrigger>
                    <SelectContent className="max-h-64">{COUNTRY_CODES.map((c) => <SelectItem key={c.dial + c.label} value={c.dial}>{c.label}</SelectItem>)}</SelectContent>
                  </Select>
                  <Input data-testid="resident-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="8111111101" className="flex-1" />
                </div>
              </div>
              <div><Label className="text-xs">Flat</Label><Input data-testid="resident-flat-input" value={form.flat} onChange={(e) => setForm({ ...form, flat: e.target.value })} placeholder="B302" className="mt-1" /></div>
              <div><Label className="text-xs">Tower</Label><Input value={form.tower} onChange={(e) => setForm({ ...form, tower: e.target.value })} placeholder="B" className="mt-1" /></div>
              <div className="col-span-2">
                <Label className="text-xs">Status</Label>
                <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                  <SelectTrigger data-testid="resident-status-select" className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Owner" data-testid="resident-status-owner">Owner</SelectItem>
                    <SelectItem value="Tenant" data-testid="resident-status-tenant">Tenant</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter><Button data-testid="save-resident-btn" onClick={create} disabled={saving || !form.name || !form.phone}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Add</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </PageHeader>

      {/* Shareable resident registration form link */}
      <div className="mb-5 rounded-xl border border-border bg-gradient-to-r from-blue-50 to-indigo-50 p-4" data-testid="resident-form-banner">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><Link2 className="h-5 w-5" /></div>
          <div className="min-w-[200px] flex-1">
            <p className="text-sm font-semibold text-slate-800">Resident self-registration link</p>
            <p className="text-xs text-slate-500">Share this link — residents fill their details and appear under Pending for your approval.</p>
          </div>
          <div className="flex w-full items-center gap-2 sm:w-auto">
            <Input data-testid="resident-form-link" readOnly value={formUrl} className="min-w-[200px] flex-1 bg-white font-mono text-xs sm:w-[340px]" onFocus={(e) => e.target.select()} />
            <Button data-testid="copy-form-link" variant="outline" size="sm" onClick={copyLink} disabled={!formUrl}><Copy className="mr-1.5 h-3.5 w-3.5" />Copy</Button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-4 flex items-center gap-2 border-b border-border">
        <button data-testid="tab-active" onClick={() => setTab("active")}
          className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${tab === "active" ? "border-primary text-primary" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>
          Active Residents <span className="ml-1 rounded-full bg-secondary px-1.5 py-0.5 text-[11px]">{active.length}</span>
        </button>
        <button data-testid="tab-pending" onClick={() => setTab("pending")}
          className={`-mb-px flex items-center border-b-2 px-4 py-2 text-sm font-medium transition-colors ${tab === "pending" ? "border-primary text-primary" : "border-transparent text-zinc-500 hover:text-zinc-700"}`}>
          Pending Residents
          <span className={`ml-1 rounded-full px-1.5 py-0.5 text-[11px] ${pending.length ? "bg-amber-100 text-amber-700" : "bg-secondary"}`}>{pending.length}</span>
        </button>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <Input data-testid="resident-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, flat, tower or phone…" className="pl-9" />
        </div>
        {tab === "active" && [["all", "All"], ["Owner", "Owners"], ["Tenant", "Tenants"]].map(([val, label]) => (
          <button key={val} type="button" data-testid={`resident-filter-${val.toLowerCase()}`} onClick={() => setStatusF(val)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${
              statusF === val ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-zinc-600 hover:bg-secondary"}`}>
            {label}
          </button>
        ))}
      </div>

      {loading ? <Loader2 className="h-6 w-6 animate-spin text-zinc-400" /> : (
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-border bg-secondary/50 text-left text-[11px] uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="px-5 py-3 font-medium">Name</th>
                <th className="px-5 py-3 font-medium">Flat</th>
                <th className="px-5 py-3 font-medium">Tower</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Phone</th>
                <th className="px-5 py-3 font-medium">Source</th>
                <th className="px-5 py-3 text-right font-medium">{tab === "pending" ? "Review" : ""}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={7} className="py-12 text-center text-sm text-zinc-400">
                  {tab === "pending" ? "No pending resident requests" : "No residents match your filters"}
                </td></tr>
              ) : filtered.map((r) => (
                <tr key={r.id} data-testid={`resident-row-${r.id}`} className="border-b border-border last:border-0 hover:bg-secondary/50">
                  <td className="px-5 py-3 font-medium">{r.name}</td>
                  <td className="px-5 py-3 text-zinc-600">{r.flat || "—"}</td>
                  <td className="px-5 py-3 text-zinc-600">{r.tower || "—"}</td>
                  <td className="px-5 py-3" data-testid={`resident-status-${r.id}`}>
                    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                      (r.status || "Owner") === "Tenant" ? "border-indigo-200 bg-indigo-50 text-indigo-700" : "border-blue-200 bg-blue-50 text-blue-700"}`}>
                      {r.status || "Owner"}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-zinc-500">{r.phone}</td>
                  <td className="px-5 py-3"><SourceBadge r={r} /></td>
                  <td className="px-5 py-3">
                    {tab === "pending" ? (
                      <div className="flex items-center justify-end gap-2">
                        <Button data-testid={`approve-resident-${r.id}`} size="sm" onClick={() => approve(r)} disabled={busyId === r.id}
                          className="h-8 bg-emerald-600 hover:bg-emerald-700">
                          {busyId === r.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="mr-1 h-3.5 w-3.5" />}Accept
                        </Button>
                        <Button data-testid={`reject-resident-${r.id}`} size="sm" variant="outline" onClick={() => reject(r)} disabled={busyId === r.id}
                          className="h-8 border-red-200 text-red-600 hover:bg-red-50">
                          <X className="mr-1 h-3.5 w-3.5" />Reject
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-end gap-3">
                        <button data-testid={`edit-resident-${r.id}`} onClick={() => openEdit(r)} className="text-zinc-400 hover:text-brand"><Pencil className="h-4 w-4" /></button>
                        <button data-testid={`delete-resident-${r.id}`} onClick={() => del(r)} className="text-zinc-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Edit resident dialog */}
      <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle className="font-cabinet">Edit Resident</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2"><Label className="text-xs">Name</Label><Input data-testid="edit-resident-name" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} className="mt-1" /></div>
            <div className="col-span-2"><Label className="text-xs">Phone</Label>
              <div className="mt-1 flex gap-2">
                <Select value={editForm.dial} onValueChange={(v) => setEditForm({ ...editForm, dial: v })}>
                  <SelectTrigger data-testid="edit-resident-country-code" className="w-[150px] shrink-0"><SelectValue /></SelectTrigger>
                  <SelectContent className="max-h-64">{COUNTRY_CODES.map((c) => <SelectItem key={c.dial + c.label} value={c.dial}>{c.label}</SelectItem>)}</SelectContent>
                </Select>
                <Input data-testid="edit-resident-phone" value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} placeholder="8111111101" className="flex-1" />
              </div>
            </div>
            <div><Label className="text-xs">Flat</Label><Input data-testid="edit-resident-flat" value={editForm.flat} onChange={(e) => setEditForm({ ...editForm, flat: e.target.value })} className="mt-1" /></div>
            <div><Label className="text-xs">Tower</Label><Input data-testid="edit-resident-tower" value={editForm.tower} onChange={(e) => setEditForm({ ...editForm, tower: e.target.value })} className="mt-1" /></div>
            <div className="col-span-2">
              <Label className="text-xs">Status</Label>
              <Select value={editForm.status} onValueChange={(v) => setEditForm({ ...editForm, status: v })}>
                <SelectTrigger data-testid="edit-resident-status" className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Owner">Owner</SelectItem>
                  <SelectItem value="Tenant">Tenant</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter><Button data-testid="save-edit-resident-btn" onClick={saveEdit} disabled={saving || !editForm.name || !editForm.phone}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Save Changes</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
