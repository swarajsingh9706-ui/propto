import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope, useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Plus, Loader2, UsersRound, Trash2, Phone, Mail } from "lucide-react";

const ROLES = ["Chairman", "Secretary", "Treasurer", "Vice Chairman", "Joint Secretary", "Member"];
const ROLE_COLOR = {
  Chairman: ["#eff6ff", "#2563eb", "#bfdbfe"],
  Secretary: ["#f5f3ff", "#7c3aed", "#ddd6fe"],
  Treasurer: ["#ecfdf5", "#059669", "#a7f3d0"],
};
const empty = { name: "", role: "Member", tower: "", phone: "", email: "" };

export default function Committee() {
  const cfg = useScope();
  const { data, loading, reload } = useFetch("/society/committee");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const members = data || [];

  const create = async () => {
    setSaving(true);
    try { await api.post("/society/committee", form, cfg); toast.success("Member added"); setOpen(false); setForm(empty); reload(); }
    catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };
  const del = async (m) => { try { await api.delete(`/society/committee/${m.id}`); reload(); toast.success("Removed"); } catch (e) { toast.error(apiError(e)); } };
  const roleColor = (r) => ROLE_COLOR[r] || ["#f1f5f9", "#475569", "#e2e8f0"];

  return (
    <div className="p-4 sm:p-6 lg:p-8" data-testid="committee-page">
      <PageHeader title="Society Committee" subtitle="Managing Committee">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild><Button data-testid="add-committee-btn"><Plus className="mr-1.5 h-4 w-4" />Add Member</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-cabinet">New Committee Member</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label className="text-xs">Name</Label><Input data-testid="committee-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" /></div>
              <div><Label className="text-xs">Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}><SelectTrigger data-testid="committee-role-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent>{ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent></Select>
              </div>
              <div><Label className="text-xs">Tower / Block</Label><Input data-testid="committee-tower-input" value={form.tower} onChange={(e) => setForm({ ...form, tower: e.target.value })} className="mt-1" placeholder="Tower A" /></div>
              <div><Label className="text-xs">Phone</Label><Input data-testid="committee-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="mt-1" placeholder="919000000001" /></div>
              <div><Label className="text-xs">Email</Label><Input data-testid="committee-email-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="mt-1" /></div>
            </div>
            <DialogFooter><Button data-testid="save-committee-btn" onClick={create} disabled={saving || !form.name}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Add Member</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </PageHeader>

      {loading ? <Loader2 className="h-6 w-6 animate-spin text-slate-400" /> :
        members.length === 0 ? <div className="rounded-lg border border-dashed p-12 text-center text-sm text-slate-400"><UsersRound className="mx-auto mb-3 h-8 w-8 text-slate-300" />No committee members yet.</div> : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {members.map((m) => {
              const [bg, fg, br] = roleColor(m.role);
              return (
                <div key={m.id} data-testid={`committee-card-${m.id}`} className="card-hover rounded-xl border border-border bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-full text-[16px] font-black" style={{ background: bg, color: fg }}>{(m.name || "?").charAt(0).toUpperCase()}</div>
                      <div>
                        <div className="text-[15px] font-bold text-slate-900">{m.name}</div>
                        <span className="mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: bg, color: fg, border: `1px solid ${br}` }}>{m.role}</span>
                      </div>
                    </div>
                    <button data-testid={`delete-committee-${m.id}`} onClick={() => del(m)} className="text-slate-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
                  </div>
                  <div className="mt-4 space-y-1.5 border-t border-border pt-3 text-[12px] text-slate-500">
                    {m.tower && <div>🏢 {m.tower}</div>}
                    {m.phone && <div className="flex items-center gap-1.5"><Phone className="h-3 w-3" />{m.phone}</div>}
                    {m.email && <div className="flex items-center gap-1.5"><Mail className="h-3 w-3" />{m.email}</div>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
    </div>
  );
}
