import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope, useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Loader2, Wrench, Trash2, Phone } from "lucide-react";

const CATEGORIES = ["Plumbing", "Electrical", "Lift", "Security", "Housekeeping", "Civil", "Parking", "Gardening", "Water Supply", "DG Set", "Pest Control"];
const empty = { name: "", phone: "", categories: [], availability: true, active: true };

export default function Vendors() {
  const cfg = useScope();
  const { data: vendors, loading, reload } = useFetch("/society/vendors");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const create = async () => {
    setSaving(true);
    try {
      await api.post("/society/vendors", form, cfg);
      toast.success("Vendor added"); setOpen(false); setForm(empty); reload();
    } catch (e) { toast.error(apiError(e)); }
    finally { setSaving(false); }
  };
  const toggleCat = (c) => setForm((f) => ({ ...f, categories: f.categories.includes(c) ? f.categories.filter((x) => x !== c) : [...f.categories, c] }));
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

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Vendor Management" subtitle="Vendors">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="add-vendor-btn"><Plus className="mr-1.5 h-4 w-4" />Add Vendor</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-cabinet">New Vendor</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label className="text-xs">Name</Label><Input data-testid="vendor-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" /></div>
              <div><Label className="text-xs">Phone (with country code)</Label><Input data-testid="vendor-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="919000000001" className="mt-1" /></div>
              <div>
                <Label className="text-xs">Categories</Label>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {CATEGORIES.map((c) => (
                    <label key={c} className="flex items-center gap-2 text-sm">
                      <Checkbox checked={form.categories.includes(c)} onCheckedChange={() => toggleCat(c)} data-testid={`vendor-cat-${c}`} />{c}
                    </label>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm"><Switch checked={form.availability} onCheckedChange={(v) => setForm({ ...form, availability: v })} />Available</label>
            </div>
            <DialogFooter><Button data-testid="save-vendor-btn" onClick={create} disabled={saving || !form.name || !form.phone}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Add Vendor</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </PageHeader>

      {loading ? <Loader2 className="h-6 w-6 animate-spin text-zinc-400" /> : (vendors || []).length === 0 ? (
        <div className="rounded-lg border border-dashed p-12 text-center text-sm text-zinc-400"><Wrench className="mx-auto mb-3 h-8 w-8 text-zinc-300" />No vendors yet.</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {vendors.map((v) => (
            <div key={v.id} data-testid={`vendor-card-${v.id}`} className="card-hover rounded-lg border border-border bg-card p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-cabinet text-lg font-bold tracking-tight">{v.name}</h3>
                  <p className="flex items-center gap-1 text-xs text-zinc-400"><Phone className="h-3 w-3" />{v.phone}</p>
                </div>
                <button data-testid={`delete-vendor-${v.id}`} onClick={() => del(v)} className="text-zinc-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {v.categories?.map((c) => <span key={c} className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium text-zinc-600">{c}</span>)}
              </div>
              {v.categories?.length > 0 && (
                <div className="mt-3 border-t border-border pt-3">
                  <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Assignment priority (1 = gets ticket first)</p>
                  <div className="space-y-1.5">
                    {v.categories.map((c) => (
                      <div key={c} className="flex items-center justify-between gap-2 text-xs">
                        <span className="text-zinc-600">{c}</span>
                        <Input
                          type="number"
                          min="1"
                          data-testid={`vendor-priority-${v.id}-${c}`}
                          defaultValue={v.priorities?.[c] || ""}
                          onBlur={(e) => { if ((v.priorities?.[c] || "") !== e.target.value) setPriority(v, c, e.target.value); }}
                          placeholder="—"
                          className="h-7 w-16 text-xs"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-xs">
                <span className="text-zinc-500">{v.resolved}/{v.assigned} resolved</span>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1.5"><span className="text-zinc-400">Avail</span><Switch data-testid={`vendor-avail-${v.id}`} checked={v.availability} onCheckedChange={(val) => update(v, { availability: val })} /></label>
                  <label className="flex items-center gap-1.5"><span className="text-zinc-400">Active</span><Switch data-testid={`vendor-active-${v.id}`} checked={v.active} onCheckedChange={(val) => update(v, { active: val })} /></label>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
