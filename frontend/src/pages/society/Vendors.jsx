import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope, useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Loader2, Wrench, Trash2, Phone } from "lucide-react";

const CATEGORIES = ["Plumbing", "Electrical", "Lift", "Security", "Housekeeping", "Civil", "Parking", "Gardening", "Water Supply", "DG Set", "Pest Control"];

const CATEGORY_COLORS = {
  Plumbing: "bg-blue-100 text-blue-700 border-blue-200",
  Electrical: "bg-amber-100 text-amber-700 border-amber-200",
  Lift: "bg-purple-100 text-purple-700 border-purple-200",
  Security: "bg-red-100 text-red-700 border-red-200",
  Housekeeping: "bg-emerald-100 text-emerald-700 border-emerald-200",
  Civil: "bg-orange-100 text-orange-700 border-orange-200",
  Parking: "bg-cyan-100 text-cyan-700 border-cyan-200",
  Gardening: "bg-green-100 text-green-700 border-green-200",
  "Water Supply": "bg-sky-100 text-sky-700 border-sky-200",
  "DG Set": "bg-yellow-100 text-yellow-700 border-yellow-200",
  "Pest Control": "bg-pink-100 text-pink-700 border-pink-200",
};
const catColor = (c) => CATEGORY_COLORS[c] || "bg-secondary text-zinc-600 border-border";
const catDot = (c) => ({
  Plumbing: "#2563eb", Electrical: "#d97706", Lift: "#7c3aed", Security: "#dc2626",
  Housekeeping: "#059669", Civil: "#ea580c", Parking: "#0891b2", Gardening: "#16a34a",
  "Water Supply": "#0284c7", "DG Set": "#ca8a04", "Pest Control": "#db2777",
}[c] || "#64748b");

const COUNTRY_CODES = [
  { dial: "91", label: "India (+91)" },
  { dial: "1", label: "USA / Canada (+1)" },
  { dial: "971", label: "UAE (+971)" },
  { dial: "44", label: "UK (+44)" },
  { dial: "65", label: "Singapore (+65)" },
  { dial: "61", label: "Australia (+61)" },
  { dial: "966", label: "Saudi Arabia (+966)" },
  { dial: "974", label: "Qatar (+974)" },
  { dial: "60", label: "Malaysia (+60)" },
  { dial: "49", label: "Germany (+49)" },
  { dial: "33", label: "France (+33)" },
  { dial: "977", label: "Nepal (+977)" },
  { dial: "880", label: "Bangladesh (+880)" },
  { dial: "94", label: "Sri Lanka (+94)" },
  { dial: "27", label: "South Africa (+27)" },
  { dial: "64", label: "New Zealand (+64)" },
];

const empty = { name: "", dial: "91", phone: "", categories: [], priorities: {}, availability: true, active: true };

export default function Vendors() {
  const cfg = useScope();
  const { data: vendors, loading, reload } = useFetch("/society/vendors");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const create = async () => {
    setSaving(true);
    try {
      const num = (form.phone || "").replace(/\D/g, "");
      const priorities = {};
      Object.entries(form.priorities).forEach(([k, val]) => { const n = parseInt(val, 10); if (!isNaN(n) && n > 0) priorities[k] = n; });
      const payload = { name: form.name, phone: form.dial + num, categories: form.categories, availability: form.availability, active: true, priorities };
      await api.post("/society/vendors", payload, cfg);
      toast.success("Vendor added"); setOpen(false); setForm(empty); reload();
    } catch (e) { toast.error(apiError(e)); }
    finally { setSaving(false); }
  };
  const toggleCat = (c) => setForm((f) => {
    const has = f.categories.includes(c);
    const categories = has ? f.categories.filter((x) => x !== c) : [...f.categories, c];
    const priorities = { ...f.priorities };
    if (has) delete priorities[c];
    return { ...f, categories, priorities };
  });
  const update = async (v, patch) => { try { await api.put(`/society/vendors/${v.id}`, patch); reload(); } catch (e) { toast.error(apiError(e)); } };
  const del = async (v) => { try { await api.delete(`/society/vendors/${v.id}`); reload(); toast.success("Removed"); } catch (e) { toast.error(apiError(e)); } };
  const setPriority = async (v, cat, val) => {
    const priorities = { ...(v.priorities || {}) };
    const n = parseInt(val, 10);
    if (val === "" || isNaN(n) || n <= 0) delete priorities[cat];
    else priorities[cat] = n;
    try { await api.put(`/society/vendors/${v.id}`, { priorities }); reload(); toast.success("Priority updated"); }
    catch (e) { toast.error(apiError(e)); }
  };

  const all = vendors || [];
  const grouped = CATEGORIES
    .map((c) => ({ cat: c, list: all.filter((v) => v.categories?.includes(c)).sort((a, b) => ((a.priorities?.[c] ?? 999) - (b.priorities?.[c] ?? 999))) }))
    .filter((g) => g.list.length > 0);
  const uncategorized = all.filter((v) => !v.categories || v.categories.length === 0);

  const VendorRow = ({ v, cat }) => (
    <div data-testid={`vendor-card-${v.id}`} className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3">
      {cat && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold" style={{ background: catDot(cat) + "22", color: catDot(cat) }} data-testid={`vendor-rank-${v.id}-${cat}`}>
          {v.priorities?.[cat] ?? "—"}
        </div>
      )}
      <div className="min-w-[140px] flex-1">
        <h3 className="font-cabinet text-base font-bold tracking-tight">{v.name}</h3>
        <p className="flex items-center gap-1 text-xs text-zinc-400"><Phone className="h-3 w-3" />{v.phone}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {v.categories?.map((c) => <span key={c} className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${catColor(c)}`}>{c}</span>)}
        </div>
      </div>
      {cat && (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-zinc-400">Priority</span>
          <Input type="number" min="1" data-testid={`vendor-priority-${v.id}-${cat}`} defaultValue={v.priorities?.[cat] || ""}
            onBlur={(e) => { if (String(v.priorities?.[cat] || "") !== e.target.value) setPriority(v, cat, e.target.value); }}
            placeholder="—" className="h-8 w-16 text-xs" />
        </div>
      )}
      <div className="flex items-center gap-3 text-xs">
        <span className="hidden text-zinc-500 sm:inline">{v.resolved}/{v.assigned}</span>
        <label className="flex items-center gap-1.5"><span className="text-zinc-400">Avail</span><Switch data-testid={`vendor-avail-${v.id}`} checked={v.availability} onCheckedChange={(val) => update(v, { availability: val })} /></label>
        <label className="flex items-center gap-1.5"><span className="text-zinc-400">Active</span><Switch data-testid={`vendor-active-${v.id}`} checked={v.active} onCheckedChange={(val) => update(v, { active: val })} /></label>
        <button data-testid={`delete-vendor-${v.id}`} onClick={() => del(v)} className="text-zinc-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
      </div>
    </div>
  );

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Vendor Management" subtitle="Vendors">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="add-vendor-btn"><Plus className="mr-1.5 h-4 w-4" />Add Vendor</Button></DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle className="font-cabinet">New Vendor</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label className="text-xs">Name</Label><Input data-testid="vendor-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" /></div>
              <div>
                <Label className="text-xs">Phone</Label>
                <div className="mt-1 flex gap-2">
                  <Select value={form.dial} onValueChange={(v) => setForm({ ...form, dial: v })}>
                    <SelectTrigger data-testid="vendor-country-code" className="w-[150px] shrink-0"><SelectValue /></SelectTrigger>
                    <SelectContent className="max-h-64">
                      {COUNTRY_CODES.map((c) => <SelectItem key={c.dial + c.label} value={c.dial}>{c.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  <Input data-testid="vendor-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="9000000001" className="flex-1" />
                </div>
              </div>
              <div>
                <Label className="text-xs">Categories</Label>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {CATEGORIES.map((c) => (
                    <label key={c} className="flex items-center gap-2 text-sm">
                      <Checkbox checked={form.categories.includes(c)} onCheckedChange={() => toggleCat(c)} data-testid={`vendor-cat-${c}`} />
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${catColor(c)}`}>{c}</span>
                    </label>
                  ))}
                </div>
              </div>
              {form.categories.length > 0 && (
                <div>
                  <Label className="text-xs">Priority per category</Label>
                  <p className="text-[10px] text-zinc-400">1 = gets the ticket first. Existing vendors at/after that slot shift down. Leave blank to add at the end.</p>
                  <div className="mt-2 space-y-1.5">
                    {form.categories.map((c) => (
                      <div key={c} className="flex items-center justify-between gap-2">
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${catColor(c)}`}>{c}</span>
                        <Input type="number" min="1" data-testid={`vendor-new-priority-${c}`} value={form.priorities[c] ?? ""}
                          onChange={(e) => setForm((f) => ({ ...f, priorities: { ...f.priorities, [c]: e.target.value } }))}
                          placeholder="auto" className="h-8 w-24 text-xs" />
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <label className="flex items-center gap-2 text-sm"><Switch checked={form.availability} onCheckedChange={(v) => setForm({ ...form, availability: v })} />Available</label>
            </div>
            <DialogFooter><Button data-testid="save-vendor-btn" onClick={create} disabled={saving || !form.name || !form.phone}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Add Vendor</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </PageHeader>

      {loading ? <Loader2 className="h-6 w-6 animate-spin text-zinc-400" /> : all.length === 0 ? (
        <div className="rounded-lg border border-dashed p-12 text-center text-sm text-zinc-400"><Wrench className="mx-auto mb-3 h-8 w-8 text-zinc-300" />No vendors yet.</div>
      ) : (
        <div className="space-y-7">
          {grouped.map(({ cat, list }) => (
            <section key={cat} data-testid={`vendor-group-${cat}`}>
              <div className="mb-3 flex items-center gap-2">
                <span className="h-3 w-3 rounded-full" style={{ background: catDot(cat) }} />
                <h2 className="font-cabinet text-lg font-bold tracking-tight">{cat}</h2>
                <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${catColor(cat)}`}>{list.length}</span>
              </div>
              <div className="space-y-2">
                {list.map((v) => <VendorRow key={v.id + cat} v={v} cat={cat} />)}
              </div>
            </section>
          ))}
          {uncategorized.length > 0 && (
            <section data-testid="vendor-group-uncategorized">
              <div className="mb-3 flex items-center gap-2">
                <span className="h-3 w-3 rounded-full bg-zinc-400" />
                <h2 className="font-cabinet text-lg font-bold tracking-tight">Uncategorized</h2>
                <span className="rounded-full border border-border bg-secondary px-2 py-0.5 text-[11px] font-semibold text-zinc-500">{uncategorized.length}</span>
              </div>
              <div className="space-y-2">
                {uncategorized.map((v) => <VendorRow key={v.id} v={v} cat={null} />)}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
