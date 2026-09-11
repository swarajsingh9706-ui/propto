import { useRef, useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope, useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Plus, Loader2, Trash2, Upload, Users, Search } from "lucide-react";

const empty = { name: "", phone: "", flat: "", tower: "", status: "Owner" };

export default function Residents() {
  const cfg = useScope();
  const { data: residents, loading, reload } = useFetch("/society/residents");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [q, setQ] = useState("");
  const [statusF, setStatusF] = useState("all");
  const fileRef = useRef();

  const create = async () => {
    setSaving(true);
    try { await api.post("/society/residents", form, cfg); toast.success("Resident added"); setOpen(false); setForm(empty); reload(); }
    catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const del = async (r) => { try { await api.delete(`/society/residents/${r.id}`); reload(); } catch (e) { toast.error(apiError(e)); } };
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

  const filtered = (residents || []).filter((r) => {
    if (statusF !== "all" && (r.status || "Owner") !== statusF) return false;
    if (q) {
      const s = q.toLowerCase();
      return [r.name, r.flat, r.tower, r.phone].some((x) => (x || "").toLowerCase().includes(s));
    }
    return true;
  });

  return (
    <div className="p-8">
      <PageHeader title="Resident Management" subtitle="Residents">        <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" onChange={importFile} className="hidden" data-testid="import-file-input" />
        <Button data-testid="import-residents-btn" variant="outline" onClick={() => fileRef.current?.click()}><Upload className="mr-1.5 h-4 w-4" />Import Excel</Button>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="add-resident-btn"><Plus className="mr-1.5 h-4 w-4" />Add Resident</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-cabinet">New Resident</DialogTitle></DialogHeader>
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2"><Label className="text-xs">Name</Label><Input data-testid="resident-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" /></div>
              <div className="col-span-2"><Label className="text-xs">Phone (with country code)</Label><Input data-testid="resident-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="918111111101" className="mt-1" /></div>
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

      <p className="mb-4 text-xs text-zinc-400">Excel/CSV columns: <span className="font-mono">name, phone, flat, tower, status</span></p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <Input data-testid="resident-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, flat, tower or phone…" className="pl-9" />
        </div>
        {[["all", "All"], ["Owner", "Owners"], ["Tenant", "Tenants"]].map(([val, label]) => (
          <button
            key={val}
            type="button"
            data-testid={`resident-filter-${val.toLowerCase()}`}
            onClick={() => setStatusF(val)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${
              statusF === val ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card text-zinc-600 hover:bg-secondary"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? <Loader2 className="h-6 w-6 animate-spin text-zinc-400" /> : (residents || []).length === 0 ? (
        <div className="rounded-lg border border-dashed p-12 text-center text-sm text-zinc-400"><Users className="mx-auto mb-3 h-8 w-8 text-zinc-300" />No residents yet.</div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="border-b border-border bg-secondary/50 text-left text-[11px] uppercase tracking-wider text-zinc-500">
              <tr><th className="px-5 py-3 font-medium">Name</th><th className="px-5 py-3 font-medium">Flat</th><th className="px-5 py-3 font-medium">Tower</th><th className="px-5 py-3 font-medium">Status</th><th className="px-5 py-3 font-medium">Phone</th><th className="px-5 py-3"></th></tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={6} className="py-12 text-center text-sm text-zinc-400">No residents match your filters</td></tr>
              ) : filtered.map((r) => (
                <tr key={r.id} data-testid={`resident-row-${r.id}`} className="border-b border-border last:border-0 hover:bg-secondary/50">
                  <td className="px-5 py-3 font-medium">{r.name}</td>
                  <td className="px-5 py-3 text-zinc-600">{r.flat || "—"}</td>
                  <td className="px-5 py-3 text-zinc-600">{r.tower || "—"}</td>
                  <td className="px-5 py-3" data-testid={`resident-status-${r.id}`}>
                    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                      (r.status || "Owner") === "Tenant"
                        ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                        : "border-blue-200 bg-blue-50 text-blue-700"}`}>
                      {r.status || "Owner"}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-zinc-500">{r.phone}</td>
                  <td className="px-5 py-3 text-right"><button data-testid={`delete-resident-${r.id}`} onClick={() => del(r)} className="text-zinc-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
