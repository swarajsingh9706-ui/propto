import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { StatusBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Building2, ArrowRight, Loader2, Search, Pencil } from "lucide-react";

const empty = { name: "", code: "", address: "", city: "", towers: "", admin_name: "", admin_email: "", admin_password: "" };
const editEmpty = { name: "", address: "", city: "", towers: "", admin_email: "", admin_password: "" };

export default function Societies() {
  const { scopeInto } = useAuth();
  const navigate = useNavigate();
  const [societies, setSocieties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState("");
  const [cityFilter, setCityFilter] = useState("all");
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState(editEmpty);
  const [savingEdit, setSavingEdit] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/super/societies");
      setSocieties(data);
    } catch (e) { toast.error(apiError(e)); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    setSaving(true);
    try {
      await api.post("/super/societies", {
        ...form,
        towers: form.towers.split(",").map((t) => t.trim()).filter(Boolean),
        admin_email: form.admin_email || null,
        admin_password: form.admin_password || null,
      });
      toast.success("Society created");
      setOpen(false); setForm(empty); load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setSaving(false); }
  };

  const openEdit = (s) => {
    setEditing(s);
    setEditForm({ name: s.name || "", address: s.address || "", city: s.city || "", towers: (s.towers || []).join(", "), admin_email: "", admin_password: "" });
  };
  const saveEdit = async () => {
    setSavingEdit(true);
    try {
      const body = { name: editForm.name, address: editForm.address, city: editForm.city, towers: editForm.towers.split(",").map((t) => t.trim()).filter(Boolean) };
      if (editForm.admin_email) body.admin_email = editForm.admin_email;
      if (editForm.admin_password) body.admin_password = editForm.admin_password;
      await api.put(`/super/societies/${editing.id}`, body);
      toast.success("Society updated"); setEditing(null); load();
    } catch (e) { toast.error(apiError(e)); } finally { setSavingEdit(false); }
  };

  const cities = Array.from(new Set(societies.map((s) => s.city).filter(Boolean)));
  const filtered = societies.filter((s) => {
    if (cityFilter !== "all" && s.city !== cityFilter) return false;
    const q = query.trim().toLowerCase();
    if (q && !(`${s.name} ${s.code} ${s.city || ""}`.toLowerCase().includes(q))) return false;
    return true;
  });

  const manage = (s) => { scopeInto(s.id); navigate("/dashboard"); };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Society Management" subtitle="Super Admin">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="add-society-btn"><Plus className="mr-1.5 h-4 w-4" /> Add Society</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="font-cabinet">New Society</DialogTitle></DialogHeader>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Name" span><Input data-testid="society-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
              <Field label="Code"><Input data-testid="society-code-input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="GRNVLY" /></Field>
              <Field label="City"><Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></Field>
              <Field label="Address" span><Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
              <Field label="Towers (comma sep)" span><Input value={form.towers} onChange={(e) => setForm({ ...form, towers: e.target.value })} placeholder="A, B, C" /></Field>
              <div className="col-span-2 mt-1 border-t border-dashed pt-3"><p className="overline">Society Admin login (optional)</p></div>
              <Field label="Admin Name"><Input value={form.admin_name} onChange={(e) => setForm({ ...form, admin_name: e.target.value })} /></Field>
              <Field label="Admin Email"><Input value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })} /></Field>
              <Field label="Admin Password" span><Input type="text" value={form.admin_password} onChange={(e) => setForm({ ...form, admin_password: e.target.value })} /></Field>
            </div>
            <DialogFooter>
              <Button data-testid="save-society-btn" onClick={create} disabled={saving || !form.name || !form.code}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Create Society
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </PageHeader>

      {!loading && societies.length > 0 && (
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <Input data-testid="society-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name, code or city…" className="pl-9" />
          </div>
          <Select value={cityFilter} onValueChange={setCityFilter}>
            <SelectTrigger data-testid="society-city-filter" className="w-48"><SelectValue placeholder="All locations" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Locations</SelectItem>
              {cities.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}

      {loading ? (
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      ) : societies.length === 0 ? (
        <Empty />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.map((s) => (
            <div key={s.id} data-testid={`society-card-${s.code}`} className="card-hover rounded-lg border border-border bg-card p-5">
              <div className="flex items-start justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-secondary">
                  <Building2 className="h-5 w-5 text-zinc-700" strokeWidth={1.75} />
                </div>
                <StatusBadge status={s.active ? "Resolved" : "Escalated"} testid={`society-status-${s.code}`} />
              </div>
              <h3 className="mt-4 font-cabinet text-lg font-bold tracking-tight">{s.name}</h3>
              <p className="text-xs text-zinc-400">{s.code} · {s.city || "—"}</p>
              <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4 text-center">
                <Metric label="Tickets" value={s.ticket_count} />
                <Metric label="Vendors" value={s.vendor_count} />
                <Metric label="Residents" value={s.resident_count} />
              </div>
              <div className="mt-4 flex items-center gap-2">
                <Button data-testid={`manage-society-${s.code}`} size="sm" className="flex-1" onClick={() => manage(s)}>
                  Manage <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </Button>
                <Button data-testid={`edit-society-${s.code}`} size="sm" variant="outline" onClick={() => openEdit(s)}>
                  <Pencil className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle className="font-cabinet">Edit Society</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Name" span><Input data-testid="edit-society-name" value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} /></Field>
            <Field label="City"><Input data-testid="edit-society-city" value={editForm.city} onChange={(e) => setEditForm({ ...editForm, city: e.target.value })} /></Field>
            <Field label="Address"><Input value={editForm.address} onChange={(e) => setEditForm({ ...editForm, address: e.target.value })} /></Field>
            <Field label="Towers (comma sep)" span><Input value={editForm.towers} onChange={(e) => setEditForm({ ...editForm, towers: e.target.value })} placeholder="A, B, C" /></Field>
            <div className="col-span-2 mt-1 border-t border-dashed pt-3"><p className="overline">Update Society Admin login (optional)</p></div>
            <Field label="Admin Email (username)" span><Input data-testid="edit-society-admin-email" value={editForm.admin_email} onChange={(e) => setEditForm({ ...editForm, admin_email: e.target.value })} placeholder="leave blank to keep current" /></Field>
            <Field label="New Password" span><Input data-testid="edit-society-admin-password" type="text" value={editForm.admin_password} onChange={(e) => setEditForm({ ...editForm, admin_password: e.target.value })} placeholder="leave blank to keep current" /></Field>
          </div>
          <DialogFooter>
            <Button data-testid="save-edit-society-btn" onClick={saveEdit} disabled={savingEdit || !editForm.name}>
              {savingEdit && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const Field = ({ label, span, children }) => (
  <div className={span ? "col-span-2" : ""}>
    <Label className="text-xs">{label}</Label>
    <div className="mt-1">{children}</div>
  </div>
);
const Metric = ({ label, value }) => (
  <div><p className="font-cabinet text-lg font-bold">{value}</p><p className="text-[10px] uppercase tracking-wider text-zinc-400">{label}</p></div>
);
const Empty = () => (
  <div className="rounded-lg border border-dashed border-border bg-card p-12 text-center">
    <Building2 className="mx-auto h-8 w-8 text-zinc-300" />
    <p className="mt-3 text-sm text-zinc-500">No societies yet. Add your first society to get started.</p>
  </div>
);
